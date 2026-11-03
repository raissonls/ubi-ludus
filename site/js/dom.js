// Small helpers for building the page with safe DOM calls only. Text is always set as text
// (textContent or a text node), never parsed as HTML, so data can never become markup.

/** Create an element: attributes by name, plain text with `text`, children appended as nodes. */
export function el(tag, attributes = {}, children = []) {
  const element = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (name === 'text') {
      element.textContent = value;
    } else {
      element.setAttribute(name, value);
    }
  }
  element.append(...children);
  return element;
}

const HEX = /^#[0-9a-fA-F]{6}$/;

/**
 * Give an element a team's two colours as CSS variables (--team-primary, --team-secondary), for
 * the style sheet to use as an accent. Colours only, never a crest. The values are checked
 * first, and set through the style object, which the Content Security Policy allows (a `style`
 * attribute in the markup it would not).
 */
export function setAccent(element, team) {
  const { primary, secondary } = team?.colors ?? {};
  if (HEX.test(primary ?? '') && HEX.test(secondary ?? '')) {
    element.style.setProperty('--team-primary', primary);
    element.style.setProperty('--team-secondary', secondary);
  }
}
