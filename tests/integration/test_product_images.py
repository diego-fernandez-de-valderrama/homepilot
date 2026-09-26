"""Real catalog + real Bauhaus CDN: most product images load, and the known dead links are detected.

Needs PostgreSQL (the `catalog` fixture skips otherwise) and internet access (skipped when offline).
"""

import urllib.error
import urllib.request

import pytest

from smart_home_agent.repositories.postgres import CatalogRepository
from smart_home_agent.ui import images
from smart_home_agent.ui.components import card_image_urls, product_cards_html

pytestmark = pytest.mark.integration

# Innr Smart Plug: its CDN image loads. Ledvance LED candle: the source data links to a deleted image (404).
WORKING_ID = "32081248"
GONE_ID = "28143758"


@pytest.fixture(scope="module")
def online() -> None:
    try:
        urllib.request.urlopen("https://media.cdn.bauhaus", timeout=5)
    except urllib.error.HTTPError:
        pass  # the host answered
    except OSError:
        pytest.skip("no internet access to media.cdn.bauhaus")


def test_real_catalog_images_render_or_fall_back(catalog: CatalogRepository, online):
    products = catalog.get_products([WORKING_ID, GONE_ID])
    assert {p.id for p in products} == {WORKING_ID, GONE_ID}
    by_id = {p.id: p for p in products}

    missing = images.find_missing_images(card_image_urls(products))
    html = product_cards_html(products, missing)

    assert by_id[GONE_ID].image_url in missing
    assert by_id[WORKING_ID].image_url not in missing
    assert f'src="{by_id[WORKING_ID].image_url}"' in html
    assert "No image" in html
