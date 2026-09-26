import json
import zipfile

from catalog_ingestion.ingestion.zip_loader import load_products
from tests.conftest import SPARSE_MATTER, build_zip, load_fixture_json


def test_skips_macos_metadata_and_reports_invalid_files(tmp_path):
    product = load_fixture_json(SPARSE_MATTER)
    zip_path = build_zip(
        tmp_path / "products.zip",
        [product],
        extra_members={
            "__MACOSX/info/._32391327.json": b"\x00\x05binary",
            "info/._hidden.json": b"\x00",
            "info/broken.json": b"{not json",
            "info/no_id.json": b'{"title": "x"}',
            "info/readme.txt": b"ignored",
        },
    )

    result = load_products(zip_path)

    assert [p.id for p in result.products] == [SPARSE_MATTER]
    assert {error.member for error in result.errors} == {"info/broken.json", "info/no_id.json"}


def test_raw_product_is_kept_verbatim(tmp_path):
    product = load_fixture_json(SPARSE_MATTER)
    result = load_products(build_zip(tmp_path / "p.zip", [product]))
    raw = result.products[0]
    assert raw.url.endswith("\n")  # the dataset URL keeps its trailing newline in the raw copy
    assert dict(raw.original) == product


def test_duplicate_ids_keep_first(tmp_path):
    product = load_fixture_json(SPARSE_MATTER)
    duplicate = {**product, "title": "changed"}
    zip_path = tmp_path / "p.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("info/a.json", json.dumps(product))
        archive.writestr("info/b.json", json.dumps(duplicate))
    result = load_products(zip_path)
    assert len(result.products) == 1
    assert result.products[0].title == product["title"]
    assert "duplicate" in result.errors[0].error
