"""The `Recommendation.notes`: what the agent must say about the list it got."""


def recommendation_notes(
    confirmed_products: int, unconfirmed_products: int, shown: int, has_other_versions: bool
) -> list[str]:
    notes: list[str] = []
    if not confirmed_products:
        notes.append("No candidate is confirmed for every requirement; do not present any product as compatible.")
    if unconfirmed_products:
        notes.append(
            f"{unconfirmed_products} candidate(s) match the need but compatibility is unknown for at least "
            "one requirement (the catalog does not say). Present them only as unconfirmed."
        )
    if confirmed_products > shown:
        notes.append(f"{confirmed_products} confirmed products in total; showing the top {shown}.")
    if has_other_versions:
        notes.append(
            "Versions of the same product (same title) share one entry; `other_versions` lists the others "
            "with their own status for this request."
        )
    return notes
