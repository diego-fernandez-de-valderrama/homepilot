from collections.abc import Sequence


class ProductNotFoundError(LookupError):
    def __init__(self, product_ids: Sequence[str]) -> None:
        self.product_ids = list(product_ids)
        super().__init__(f"product(s) not found in the catalog: {', '.join(self.product_ids)}")
