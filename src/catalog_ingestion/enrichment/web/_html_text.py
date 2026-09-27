import json
import re

from bs4 import BeautifulSoup


class HtmlText:
    """HTML -> plain text focused on product information."""

    _NOISE_TAGS = ("script", "style", "noscript", "svg", "nav", "header", "footer", "form", "iframe")
    _WHITESPACE = re.compile(r"[ \t\r\f\v]+")
    _BLANK_LINES = re.compile(r"\n{2,}")

    @staticmethod
    def to_text(html: str, max_chars: int) -> str:
        soup = BeautifulSoup(html, "html.parser")
        structured = HtmlText._json_ld_products(soup)
        for tag in soup(HtmlText._NOISE_TAGS):
            tag.decompose()
        main = soup.find("main") or soup.body or soup
        lines = (HtmlText._WHITESPACE.sub(" ", line).strip() for line in main.get_text("\n").splitlines())
        body = HtmlText._BLANK_LINES.sub("\n", "\n".join(line for line in lines if line))
        text = "\n\n".join([*structured, body]).strip()
        return text[:max_chars]

    @staticmethod
    def _json_ld_products(soup: BeautifulSoup) -> list[str]:
        """Product descriptions from schema.org JSON-LD blocks, when present."""
        texts: list[str] = []
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string or "")
            except json.JSONDecodeError:
                continue
            for item in data if isinstance(data, list) else [data]:
                if isinstance(item, dict) and item.get("@type") == "Product":
                    parts = [str(item.get(key, "")) for key in ("name", "description") if item.get(key)]
                    brand = item.get("brand")
                    if isinstance(brand, dict) and brand.get("name"):
                        parts.append(f"Brand: {brand['name']}")
                    texts.append("\n".join(parts))
        return texts
