class CartChangeError(ValueError):
    """Products of a change that cannot be applied; `errors` has one entry per product with its reason."""

    def __init__(self, errors: list[dict[str, str]]) -> None:
        super().__init__("; ".join(f"{e['product_id']}: {e['message']}" for e in errors))
        self.errors = errors

    @property
    def status(self) -> str:
        return "not_found" if all(e["status"] == "not_found" for e in self.errors) else "invalid_input"
