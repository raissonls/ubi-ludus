// "Copy the link to this view" (FR-29). The link is the page's address plus the filters and the
// visitor's own teams and services, so it only exists when they ask for it. It is copied to the
// clipboard; when the browser refuses (no permission, an old browser) it is also shown in a box,
// ready to select.

/**
 * @param link  a function giving the address to share, built when the button is pressed
 */
export function createShare({ translator, link }) {
  const button = document.getElementById('share-copy');
  const box = document.getElementById('share-link');
  const status = document.getElementById('share-status');

  button.addEventListener('click', async () => {
    const address = link();
    box.value = address;
    box.hidden = false;
    try {
      await navigator.clipboard.writeText(address);
      status.textContent = translator.t('share.copied');
    } catch {
      status.textContent = translator.t('share.manual');
      box.focus();
      box.select();
    }
  });
}
