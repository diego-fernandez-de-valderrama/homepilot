import json
import zipfile
from pathlib import Path

import pytest

from catalog_ingestion.models import NormalizedProduct, RawProduct, RawProductMapper, RawProductSchema
from catalog_ingestion.preparation import ProductNormalizer

FIXTURES = Path(__file__).parent / "fixtures" / "products"

# Real products from products.zip, chosen for their particularities.
SPARSE_MATTER = "32391327"  # empty description + attributes, Matter only in the title
RICH_SCHELLENBERG = "22512378"  # full description + attributes
DISCOUNTED = "33208183"  # multi-line discounted price
DANGLING_ATTRIBUTE = "31698195"  # one attribute section with an odd number of lines
HUE_BRIDGE = "26010740"  # "Philips Hue App + Google Home", mentions HomeKit in description
HOMEMATIC_OR = "26735292"  # "Access Point; Zentrale CCU3; Partnerlösungen"
HOMEMATIC_STANDALONE = "27103041"  # includes "Stand-alone (Push-to-Pair)"
RING_SUBSCRIPTION = "27256662"  # "Abonnement bei Ring (nicht enthalten) notwendig"
BOSCH_CONTROLLER = "25181740"  # "nur in Verbindung mit dem Bosch Smart Home Controller", slug: alarm systems
HUE_MOTION = "26011318"  # "Philips Hue App + Apple Homekit" inside Smarte Steuerung
AQARA_THREAD = "32072844"  # Thread + "Samsung SmartThings und Aqara Home"
SHELLY_ZWAVE = "31507255"  # Z-Wave Plus + professional installation
HOMEMATIC_CCU2 = "28838063"  # "Nicht mehr kompatibel mit der Zentrale CCU2"; Apple Siri without HomeKit
TCL_INSTALLATION = "25816769"  # Installationshinweis: Fachhandwerker
THOMSON_NO_DESCRIPTION = "23197529"  # attributes but no description


def load_fixture_json(product_id: str) -> dict:
    return json.loads((FIXTURES / f"{product_id}.json").read_text("utf-8"))


def load_raw(product_id: str) -> RawProduct:
    data = load_fixture_json(product_id)
    return RawProductMapper.from_schema(RawProductSchema.model_validate(data), original=data)


def load_normalized(product_id: str) -> NormalizedProduct:
    return ProductNormalizer.normalize(load_raw(product_id))


def build_zip(path: Path, products: list[dict], extra_members: dict[str, bytes] | None = None) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for product in products:
            archive.writestr(f"info/{product['id']}.json", json.dumps(product, ensure_ascii=False))
        for name, payload in (extra_members or {}).items():
            archive.writestr(name, payload)
    return path


@pytest.fixture
def all_fixture_ids() -> list[str]:
    return sorted(path.stem for path in FIXTURES.glob("*.json"))
