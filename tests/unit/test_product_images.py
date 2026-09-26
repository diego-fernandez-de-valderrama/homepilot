"""Product card images: working URLs are rendered as <img>, URLs the server reports as gone get a placeholder.

A local HTTP server stands in for the CDN, so this runs offline and deterministically.
"""

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from smart_home_agent.ui import images
from smart_home_agent.ui.components import card_image_urls, product_cards_html
from tests.fakes import product

IMAGE_BODY = b"RIFF\x00\x00\x00\x00WEBP"  # only the status code matters to the check


class _FakeCdn(BaseHTTPRequestHandler):
    def _respond(self, body: bool) -> None:
        if self.path.startswith("/ok/"):
            self.send_response(200)
            self.send_header("Content-Type", "image/webp")
            self.send_header("Content-Length", str(len(IMAGE_BODY)))
            self.end_headers()
            if body:
                self.wfile.write(IMAGE_BODY)
        elif self.path.startswith("/slow/"):
            self.send_response(503)  # a server error is not proof that the image is gone
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_HEAD(self) -> None:
        self._respond(body=False)

    def do_GET(self) -> None:
        self._respond(body=True)

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture(scope="module")
def cdn() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeCdn)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _with_image(product_id: str, url: str | None):
    return product(product_id, title=f"Plug {product_id}").model_copy(update={"image_url": url})


def test_working_images_are_shown_and_gone_ones_are_left_out(cdn):
    working = [_with_image("30000001", f"{cdn}/ok/a.webp"), _with_image("30000002", f"{cdn}/ok/b.webp")]
    gone = _with_image("30000003", f"{cdn}/m/695676-2/prod_large_square.webp")
    no_url = _with_image("30000004", None)
    products = [*working, gone, no_url]

    missing = images.find_missing_images(card_image_urls(products))
    html = product_cards_html(products, missing)

    assert missing == frozenset({gone.image_url})
    for p in working:
        assert f'<img class="hp-card__image" src="{p.image_url}"' in html
    assert gone.image_url not in html
    assert html.count("hp-card--no-image") == 2  # the 404 URL and the product without any URL


def test_server_errors_and_unreachable_hosts_keep_the_image(cdn):
    unreachable = "http://127.0.0.1:9/nothing-listens-here.webp"
    urls = (f"{cdn}/slow/c.webp", unreachable)
    assert images.find_missing_images(urls) == frozenset()
