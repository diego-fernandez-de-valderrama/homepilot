from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from catalog_ingestion.core import Hashing
from catalog_ingestion.database._record_builder import RecordBuilder
from catalog_ingestion.database.records import (
    CompatibilityRecord,
    IngestionRunRecord,
    ProductRecord,
    RetrievalDocumentRecord,
    WebPageRecord,
)
from catalog_ingestion.database.upsert_outcome import UpsertOutcome
from catalog_ingestion.models import (
    CatalogProductMapper,
    CatalogProductSchema,
    EnrichedProduct,
    ProductState,
    RawProduct,
    RetrievalDocument,
    WebPage,
)


class PostgresRepository:
    """PostgreSQL persistence through SQLAlchemy. All writes for one product happen in one transaction."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    # --- state used for idempotency decisions --------------------------------------------

    def load_states(self) -> dict[str, ProductState]:
        statement = select(
            ProductRecord.id,
            ProductRecord.raw_hash,
            ProductRecord.document_hash,
            ProductRecord.enrichment_hash,
            ProductRecord.llm_output,
            ProductRecord.enrichment_model,
            ProductRecord.prompt_version,
            ProductRecord.active,
        )
        with self._sessions() as session:
            return {
                row.id: ProductState(
                    raw_hash=row.raw_hash,
                    document_hash=row.document_hash,
                    enrichment_hash=row.enrichment_hash,
                    llm_output=row.llm_output,
                    enrichment_model=row.enrichment_model,
                    prompt_version=row.prompt_version,
                    active=row.active,
                )
                for row in session.execute(statement)
            }

    # --- web page cache ------------------------------------------------------------------

    def load_web_pages(self) -> dict[str, WebPage]:
        with self._sessions() as session:
            return {record.url: RecordBuilder.web_page(record) for record in session.scalars(select(WebPageRecord))}

    def save_web_page(self, product_id: str, page: WebPage) -> None:
        with self._sessions.begin() as session:
            session.merge(RecordBuilder.web_page_record(product_id, page))

    # --- products ------------------------------------------------------------------------

    def upsert_product(
        self,
        enriched: EnrichedProduct,
        raw: RawProduct,
        raw_hash: str,
        enrichment_hash: str | None,
        llm_output: dict[str, Any] | None,
    ) -> UpsertOutcome:
        document = CatalogProductMapper.to_schema(enriched).model_dump(mode="json")
        document_hash = Hashing.sha256_json(document)
        product = enriched.product

        with self._sessions.begin() as session:
            record = session.get(ProductRecord, product.id)
            if (
                record is not None
                and record.raw_hash == raw_hash
                and record.document_hash == document_hash
                and record.enrichment_hash == enrichment_hash
                and record.active
            ):
                return UpsertOutcome.UNCHANGED

            outcome = UpsertOutcome.UPDATED
            if record is None:
                record = ProductRecord(id=product.id)
                session.add(record)
                outcome = UpsertOutcome.INSERTED

            record.active = True
            record.title = product.title
            record.brand = enriched.brand
            record.category = enriched.category
            record.category_slug = product.category_slug
            record.product_type = enriched.product_type
            record.is_smart_home = product.is_smart_home
            record.price_value = product.price.value
            record.price_currency = product.price.currency
            record.original_price = product.price.original_value
            record.ean = product.ean
            record.image_url = product.image_url
            record.source_url = product.source_url
            record.summary_en = enriched.summary_en
            record.summary_de = enriched.summary_de
            record.completeness_level = enriched.completeness.level.value
            record.completeness_score = enriched.completeness.score
            record.web_status = enriched.web_status.value
            record.raw = dict(raw.original)
            record.document = document
            record.attributes = RecordBuilder.attributes_json(enriched)
            record.llm_output = llm_output
            record.raw_hash = raw_hash
            record.document_hash = document_hash
            record.enrichment_hash = enrichment_hash
            record.enrichment_model = enriched.enrichment_model
            record.prompt_version = enriched.prompt_version
            # delete-orphan cascade replaces the previous child rows
            record.compatibility = [RecordBuilder.compatibility(fact) for fact in enriched.compatibility]
            record.requirements = [RecordBuilder.requirement(req) for req in enriched.requirements]
        return outcome

    def deactivate_missing(self, present_ids: Iterable[str]) -> list[str]:
        present = list(present_ids)
        if not present:  # `NOT IN ()` would match every row: never deactivate the whole catalog
            return []
        statement = (
            update(ProductRecord)
            .where(ProductRecord.active, ProductRecord.id.not_in(present))
            .values(active=False, updated_at=func.now())
            .returning(ProductRecord.id)
        )
        with self._sessions.begin() as session:
            return list(session.scalars(statement))

    def inactive_ids(self) -> list[str]:
        with self._sessions() as session:
            statement = select(ProductRecord.id).where(~ProductRecord.active).order_by(ProductRecord.id)
            return list(session.scalars(statement))

    def load_enriched(self, product_ids: list[str] | None = None) -> list[EnrichedProduct]:
        statement = select(ProductRecord.document).where(ProductRecord.active).order_by(ProductRecord.id)
        if product_ids is not None:
            statement = statement.where(ProductRecord.id.in_(product_ids))
        with self._sessions() as session:
            documents = session.scalars(statement).all()
        return [
            CatalogProductMapper.from_schema(CatalogProductSchema.model_validate(document)) for document in documents
        ]

    # --- retrieval documents -------------------------------------------------------------

    def save_document(self, document: RetrievalDocument) -> None:
        with self._sessions.begin() as session:
            record = session.get(RetrievalDocumentRecord, document.product_id)
            if record is None:
                session.add(
                    RetrievalDocumentRecord(
                        product_id=document.product_id, text=document.text, doc_hash=document.doc_hash
                    )
                )
            elif record.doc_hash != document.doc_hash:
                record.text = document.text
                record.doc_hash = document.doc_hash

    def mark_indexed(self, documents: list[RetrievalDocument], embedding_model: str) -> None:
        if not documents:
            return
        now = datetime.now(UTC)
        with self._sessions.begin() as session:
            session.execute(
                update(RetrievalDocumentRecord),
                [
                    {
                        "product_id": doc.product_id,
                        "indexed_doc_hash": doc.doc_hash,
                        "embedding_model": embedding_model,
                        "indexed_at": now,
                    }
                    for doc in documents
                ],
            )

    def clear_indexed(self, product_ids: list[str]) -> None:
        """Forgets the index state of products whose Qdrant points were deleted."""
        if not product_ids:
            return
        with self._sessions.begin() as session:
            session.execute(
                update(RetrievalDocumentRecord)
                .where(
                    RetrievalDocumentRecord.product_id.in_(product_ids),
                    RetrievalDocumentRecord.indexed_doc_hash.is_not(None),
                )
                .values(indexed_doc_hash=None, embedding_model=None, indexed_at=None)
            )

    # --- runs & status -------------------------------------------------------------------

    def start_run(self, args: dict[str, Any]) -> int:
        """Records a new run. Runs left in `running` were killed without cleanup (runs are not
        expected to overlap), so they are marked `abandoned`."""
        with self._sessions.begin() as session:
            session.execute(
                update(IngestionRunRecord)
                .where(IngestionRunRecord.status == "running")
                .values(status="abandoned", finished_at=func.now())
            )
            run = IngestionRunRecord(args=args)
            session.add(run)
            session.flush()
            return run.id

    def finish_run(self, run_id: int, status: str, stats: dict[str, Any]) -> None:
        with self._sessions.begin() as session:
            run = session.get_one(IngestionRunRecord, run_id)
            run.finished_at = datetime.now(UTC)
            run.status = status
            run.stats = stats

    def status(self) -> dict[str, Any]:
        with self._sessions() as session:
            products = session.execute(
                select(
                    func.count().filter(ProductRecord.active).label("active"),
                    func.count().filter(~ProductRecord.active).label("inactive"),
                    func.count()
                    .filter(ProductRecord.active, ProductRecord.enrichment_hash.is_not(None))
                    .label("llm_enriched"),
                )
            ).one()
            levels = session.execute(
                select(ProductRecord.completeness_level, func.count())
                .where(ProductRecord.active)
                .group_by(ProductRecord.completeness_level)
                .order_by(ProductRecord.completeness_level)
            ).all()
            web = session.execute(
                select(ProductRecord.web_status, func.count())
                .where(ProductRecord.active)
                .group_by(ProductRecord.web_status)
                .order_by(ProductRecord.web_status)
            ).all()
            facts = session.execute(
                select(CompatibilityRecord.method, func.count())
                .group_by(CompatibilityRecord.method)
                .order_by(CompatibilityRecord.method)
            ).all()
            last_run = session.scalars(
                select(IngestionRunRecord).order_by(IngestionRunRecord.id.desc()).limit(1)
            ).first()
            return {
                "products": dict(products._mapping),
                "completeness": {level: count for level, count in levels},
                "web_status": {status: count for status, count in web},
                "compatibility_facts_by_method": {method: count for method, count in facts},
                "last_run": (
                    {
                        "id": last_run.id,
                        "started_at": last_run.started_at,
                        "finished_at": last_run.finished_at,
                        "status": last_run.status,
                        "stats": last_run.stats,
                    }
                    if last_run
                    else None
                ),
            }
