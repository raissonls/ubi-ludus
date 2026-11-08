// A football shirt drawn in a team's two colours: the body in the first, the collar and cuffs in
// the second. It stands where a crest would, but it is only colours (PRD R5: no crests or logos).
// Built with createElementNS and attributes only, so nothing is parsed as markup, and the colours
// are checked first: anything that is not #rrggbb becomes a neutral grey.

const SVG_NS = 'http://www.w3.org/2000/svg';
const HEX = /^#[0-9a-fA-F]{6}$/;
const FALLBACK = '#9aa0ad';

const BODY = 'M20 6L8 12L2 26L12 30L16 24V58H48V24L52 30L62 26L56 12L44 6C42 11 38 13 32 13C26 13 22 11 20 6Z';
const COLLAR = 'M20 6C22 11 26 13 32 13C38 13 42 11 44 6';
const CUFFS = 'M3.5 24.5L12.5 28.5M60.5 24.5L51.5 28.5';

/** The two colours to draw with: each must be #rrggbb, else it is a neutral grey. */
export function safeColours(colours) {
  const pick = (value) => (typeof value === 'string' && HEX.test(value) ? value : FALLBACK);
  return { primary: pick(colours?.primary), secondary: pick(colours?.secondary) };
}

function node(name, attributes) {
  const element = document.createElementNS(SVG_NS, name);
  for (const [attribute, value] of Object.entries(attributes)) {
    element.setAttribute(attribute, value);
  }
  return element;
}

/** An <svg> shirt, hidden from screen readers (the team's name always sits beside it). */
export function createShirt(colours, size = 64) {
  const { primary, secondary } = safeColours(colours);
  const svg = node('svg', {
    class: 'shirt',
    viewBox: '0 0 64 64',
    width: String(size),
    height: String(size),
    'aria-hidden': 'true',
    focusable: 'false',
  });
  svg.append(
    node('path', { class: 'shirt__body', d: BODY, fill: primary }),
    node('path', { class: 'shirt__trim', d: COLLAR, fill: 'none', stroke: secondary }),
    node('path', { class: 'shirt__trim', d: CUFFS, fill: 'none', stroke: secondary }),
  );
  return svg;
}
