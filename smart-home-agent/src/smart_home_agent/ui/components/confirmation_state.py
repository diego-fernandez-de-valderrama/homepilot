from typing import Literal

# Card state after the customer's decision (None: still open). "expired": a new message was sent instead.
type ConfirmationState = Literal["confirmed", "cancelled", "expired"] | None
