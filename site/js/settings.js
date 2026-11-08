// The settings panel: the visitor's teams and services and the filters, in a panel that slides in
// from the right. It is a native <dialog>, so the browser keeps the focus inside, makes the page
// behind inert, closes it on Escape and gives the focus back to what opened it. The sections it
// holds are drawn by their own modules (teams-picker.js, services-picker.js, filters-view.js);
// this only opens and closes it.

export function createSettings() {
  const dialog = document.getElementById('settings');
  const close = document.getElementById('settings-close');

  function open() {
    if (!dialog.open) dialog.showModal();
    dialog.querySelector('.drawer__body')?.scrollTo?.(0, 0);
  }

  document.getElementById('settings-open').addEventListener('click', open);
  close.addEventListener('click', () => dialog.close());
  // A press on the dim area (the dialog element itself, outside the panel) closes it.
  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) dialog.close();
  });

  return {
    open,
    /** Open the panel with the filters unfolded and the competition in focus. */
    openFilters() {
      open();
      const filters = document.getElementById('filters');
      filters.open = true;
      document.getElementById('filter-competition').focus();
    },
    close: () => dialog.close(),
    isOpen: () => dialog.open,
  };
}
