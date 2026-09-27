import uuid

from catalog_ingestion.storage.qdrant.repository import point_id


def test_canonical_numeric_ids_are_used_directly():
    assert point_id("32391327") == 32391327


def test_non_canonical_ids_map_to_distinct_uuids():
    assert point_id("007") != point_id("7")
    for product_id in ("007", "²", "12a", str(2**64)):
        assert isinstance(uuid.UUID(str(point_id(product_id))), uuid.UUID)
