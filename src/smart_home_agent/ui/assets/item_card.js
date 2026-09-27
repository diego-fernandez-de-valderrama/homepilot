// Product chip hover card: opens upward by default (the newest answer sits above the pinned chat input) and
// flips downward when there is not enough room above the chip, below the pinned masthead.
// Static code loaded once per page; it only toggles a CSS class and never reads the answer text.
(() => {
  if (window.__hpItemCard) return;
  window.__hpItemCard = true;
  const GAP = 8;
  const TYPICAL_CARD_HEIGHT = 320; // used when the card is not laid out yet

  function place(event) {
    const chip = event.target.closest && event.target.closest(".hp-item");
    if (!chip) return;
    const card = chip.querySelector(".hp-item__card");
    if (!card) return;
    const masthead = document.querySelector(".hp-masthead");
    const top = masthead ? masthead.getBoundingClientRect().bottom : 0;
    const room = chip.getBoundingClientRect().top - top;
    chip.classList.toggle("hp-item--below", room < (card.offsetHeight || TYPICAL_CARD_HEIGHT) + GAP);
  }

  document.addEventListener("mouseover", place, true);
  document.addEventListener("focusin", place, true);
})();
