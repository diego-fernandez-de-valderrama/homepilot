import logging
import threading

from pydantic import ValidationError

from catalog_ingestion.core import LogSetup, QuotaExhaustedError
from catalog_ingestion.enrichment.enrichment_key import EnrichmentKey
from catalog_ingestion.enrichment.enrichment_policy import EnrichmentPolicy
from catalog_ingestion.enrichment.enrichment_result import EnrichmentResult
from catalog_ingestion.enrichment.llm import Enricher, LLMResult, PromptBuilder
from catalog_ingestion.enrichment.validation import Validator
from catalog_ingestion.enrichment.web import WebRetriever
from catalog_ingestion.models import ProductState, WebPage
from catalog_ingestion.preparation import PreparedProduct
from catalog_ingestion.vocabulary import WebStatus

logger = logging.getLogger(__name__)


class ProductEnricher:
    """Enriches one prepared product: web page (if needed) -> LLM output (cached or new) -> validation.

    Runs in worker threads: only external I/O (web, Gemini), no database access. A failure is returned
    as an `EnrichmentResult` without `enriched`, never raised.
    """

    def __init__(
        self,
        web: WebRetriever | None,
        enricher: Enricher | None,
        validator: Validator,
        model_name: str,
    ) -> None:
        self._web = web
        self._enricher = enricher
        self._validator = validator
        self._model = model_name
        # Set when Gemini reports a quota that will not reset during this run (e.g. per day).
        self._llm_quota_exhausted = threading.Event()

    def start_run(self) -> None:
        """A new run may have a fresh quota."""
        self._llm_quota_exhausted.clear()

    def enrich(
        self,
        item: PreparedProduct,
        state: ProductState | None,
        web_cache: dict[str, WebPage],
        policy: EnrichmentPolicy,
    ) -> EnrichmentResult:
        product_id = item.product.id
        try:
            web_status, web_page, fetched = self._web_stage(item, web_cache, policy)

            llm_result: LLMResult | None = None
            llm_status = "skipped"
            input_hash = EnrichmentKey.current(item, web_page, PromptBuilder.VERSION)
            result_hash: str | None = input_hash
            if not policy.force and state is not None and self._is_cached(item, state, web_page, input_hash):
                llm_result = self._stored_result(product_id, state)
                if llm_result is not None:
                    llm_status = "cached"
            if llm_result is None:
                llm_result, llm_status = self._call_llm(item, web_page, policy)
            kept_previous = False
            if llm_result is None and state is not None and state.llm_output is not None:
                # No new result: keep the stored output (re-validated below against the current sources)
                # under its old hash, so the product still counts as stale and is re-enriched later.
                llm_result = self._stored_result(product_id, state)
                kept_previous = llm_result is not None
                result_hash = state.enrichment_hash

            enriched = self._validator.validate(
                product=item.product,
                completeness=item.completeness,
                facts=item.facts,
                requirements=item.requirements,
                web_status=web_status,
                web_page=web_page,
                llm=llm_result.enrichment if llm_result else None,
                enrichment_model=llm_result.model if llm_result else None,
                prompt_version=llm_result.prompt_version if llm_result else None,
            )
            return EnrichmentResult(
                prepared=item,
                enriched=enriched,
                fetched_page=fetched,
                llm_output=llm_result.raw_output if llm_result else None,
                enrichment_hash=result_hash if llm_result else None,
                llm_status=llm_status,
                kept_previous_llm=kept_previous,
            )
        except Exception as exc:
            logger.exception("Product processing failed", extra=LogSetup.fields(product_id=product_id))
            return EnrichmentResult(item, None, None, None, None, "failed", error=f"{type(exc).__name__}: {exc}")

    def _call_llm(
        self, item: PreparedProduct, web_page: WebPage | None, policy: EnrichmentPolicy
    ) -> tuple[LLMResult | None, str]:
        """A new LLM result and the `llm_status` (called | skipped | skipped_quota | failed)."""
        if self._enricher is None or policy.skip_llm:
            return None, "skipped"
        if self._llm_quota_exhausted.is_set():
            return None, "skipped_quota"
        try:
            return self._enricher.enrich(item.product, item.facts, item.requirements, web_page), "called"
        except QuotaExhaustedError as exc:
            if not self._llm_quota_exhausted.is_set():
                self._llm_quota_exhausted.set()
                logger.error(
                    "Gemini quota exhausted: LLM enrichment is skipped for the rest of this run. "
                    "Products keep their stored data; re-run `ingest` later to enrich them.",
                    extra=LogSetup.fields(error=str(exc)),
                )
        except Exception as exc:
            logger.warning("LLM enrichment failed", extra=LogSetup.fields(product_id=item.product.id, error=str(exc)))
        return None, "failed"

    def _stored_result(self, product_id: str, state: ProductState) -> LLMResult | None:
        """The stored LLM output, or None when it no longer matches the output schema."""
        assert state.llm_output is not None
        try:
            # Keep the model that actually produced the output (provenance), whatever is configured now.
            return LLMResult.from_cached(
                state.llm_output, state.enrichment_model or self._model, state.prompt_version or PromptBuilder.VERSION
            )
        except ValidationError as exc:
            logger.warning(
                "Stored LLM output is unreadable, re-enriching",
                extra=LogSetup.fields(product_id=product_id, error=str(exc)),
            )
            return None

    @staticmethod
    def _is_cached(item: PreparedProduct, state: ProductState, web_page: WebPage | None, input_hash: str) -> bool:
        if state.llm_output is None or state.enrichment_hash is None:
            return False
        if state.enrichment_hash == input_hash:
            return True
        # Results stored with an older key format are still valid (and re-stored under the new key).
        if state.enrichment_hash == EnrichmentKey.previous(item, web_page, PromptBuilder.VERSION):
            return True
        return state.enrichment_model is not None and state.enrichment_hash == EnrichmentKey.legacy(
            item, web_page, state.enrichment_model, PromptBuilder.VERSION
        )

    def _web_stage(
        self, item: PreparedProduct, web_cache: dict[str, WebPage], policy: EnrichmentPolicy
    ) -> tuple[WebStatus, WebPage | None, WebPage | None]:
        """Returns (status, page used for enrichment, newly fetched page to persist)."""
        url = item.product.source_url
        if not item.completeness.needs_web or url is None:
            return WebStatus.NOT_NEEDED, None, None
        cached = web_cache.get(url)
        can_fetch = self._web is not None and not policy.skip_web
        if cached is not None:
            retry = can_fetch and (policy.refresh_web or (self._web is not None and self._web.should_retry(cached)))
            if not retry:
                return (WebStatus.OK if cached.ok else WebStatus.FAILED), cached, None
        if not can_fetch:
            return WebStatus.SKIPPED, None, None
        assert self._web is not None
        page = self._web.retrieve(url)
        if not page.ok and cached is not None and cached.ok:
            # A failed refresh never replaces a good cached page.
            logger.info("Web refresh failed, keeping the cached page", extra=LogSetup.fields(url=url, error=page.error))
            return WebStatus.OK, cached, None
        return (WebStatus.OK if page.ok else WebStatus.FAILED), page, page
