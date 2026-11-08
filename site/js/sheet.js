// The details of one match, in a sheet that slides up over the page: it is a native <dialog>, so the
// browser keeps the focus inside, makes the page behind inert, closes it on Escape and gives the
// focus back to the poster that opened it. What is in it is the full match card (js/match-card.js):
// every broadcaster, whether the visitor can watch, the calendar and the report link.

/** @param onShown called with the list that holds the card, once it is in, to start its clock */
export function createSheet({ onShown = () => {} } = {}) {
  const dialog = document.getElementById('match-sheet');
  const list = document.getElementById('match-sheet-card');
  const close = document.getElementById('match-sheet-close');

  close.addEventListener('click', () => dialog.close());
  // A press on the dim area around the sheet (the dialog element itself) closes it.
  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) dialog.close();
  });
  dialog.addEventListener('close', () => list.replaceChildren());

  return {
    /** Show this full card (an <li>) in the sheet. */
    open(card) {
      list.replaceChildren(card);
      dialog.setAttribute('aria-labelledby', `${card.id}-title`);
      onShown(list);
      if (!dialog.open) dialog.showModal();
    },
    close: () => dialog.close(),
    isOpen: () => dialog.open,
  };
}
