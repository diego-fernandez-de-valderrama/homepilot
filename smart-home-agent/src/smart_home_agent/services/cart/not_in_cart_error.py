class NotInCartError(ValueError):
    def __init__(self, product_id: str) -> None:
        super().__init__(f"Product {product_id} is not in the cart.")
        self.product_id = product_id
