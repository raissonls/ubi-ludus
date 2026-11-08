# Performance

How fast and light the site is held to be, and how that is checked (PRD NFR performance, success measure S8, M5-02).

## The targets

For a phone on a simulated 4G connection (Lighthouse's mobile mode):

| Measure | Target |
| --- | --- |
| Lighthouse Performance, Accessibility, Best Practices, SEO | **90 or more** each |
| Largest Contentful Paint (when the main content is drawn) | **2.5 s or less** |
| Layout shift (does the page jump while it loads?) | **0.1 or less** |
| Total blocking time | 200 ms or less |
| JavaScript sent over the network | **100 KB gzipped or less** |

## Where it stands (2026-11-07)

Before M5-02, on the live site: Accessibility, Best Practices and SEO were already 100, LCP was 1.2 s, nothing blocked, and JavaScript was 43 KB. **Performance was 76, because of one number: a layout shift of 1.08.** The page is at least a screen tall, so at first paint the footer sat at the bottom of the screen; when the matches arrived the page grew to about 3,700 px and the footer jumped far below it. In addition the header and the headings grew as their text (which is filled in from the strings file) arrived, pushing the page down.

The fix keeps the room of each thing from the first paint (`site/css/base.css`): the page is at least one screen tall (so the footer starts below the fold), and the app name, the page title, the section title and the freshness line each keep their line's height. A hidden freshness line is `visibility: hidden`, not `display: none`, so its room stays. Layout shift is now 0.01 to 0.04 at every width from 320 to 1280 px, with fresh data and with old data.

On the same data, served the way GitHub Pages serves it: Performance 99, Accessibility 100, Best Practices 100, SEO 100, LCP 1.99 s, layout shift 0.018, blocking time 0, JavaScript 43 KB.

Things that are not fixable on GitHub Pages and are fine: Pages sends a ten-minute cache for every file (Lighthouse notes it, but it does not affect the score), and it cannot send other headers. The site loads 28 small script files as ES modules; it measures well, so they are not bundled (that would add a build step for no gain).

## How it is checked

- **Every pull request:** `tests/unit/test_lighthouse.py` checks that the JavaScript is far inside 100 KB gzipped. `tests/browser/test_layout_shift.py` loads the page the way a visitor's browser does and fails if it jumps by 0.1 or more, at three widths (320, 375 and 1280 px), in both themes, with fresh and with old data, with the week list and with choices made.
- **Every push to `main` that touches the site, and after each daily deploy:** `.github/workflows/lighthouse.yml` runs Lighthouse (version 12.8.2, exact) three times and uses the middle value of each number, because one run varies. The first job serves this commit's code the way Pages does (gzip, ten minutes of cache) on the data published now; the second measures the real deployed site. A miss fails the run and GitHub tells you. The table is on the run's summary page.
- **The rules** are in `src/ubi_ludus/quality/lighthouse.py` (the targets, the middle value, the table, and the small Pages-like server).

## Measuring by hand

```bash
python -m ubi_ludus.quality.lighthouse serve --site site --data site/data
```

and in another terminal, with Chrome installed (the version in `lighthouse.yml`; Node 18 or newer):

```bash
npx lighthouse@12.8.2 http://127.0.0.1:8765/ --only-categories=performance,accessibility,best-practices,seo --output=json --output-path=lh-1.json
python -m ubi_ludus.quality.lighthouse check lh-1.json
```

Run the middle line two or three times for a steadier number. Lighthouse 13 needs Node 22.

## When something drifts

| Number | Usual cause | Look at |
| --- | --- | --- |
| Layout shift up | something above the content grows after it arrives: text that is filled in later, a banner, an image without a size | `test_layout_shift.py` names what moved; give it its room in `base.css` |
| LCP up | a bigger first paint: more scripts in the first chain, a large new element | the Lighthouse report's "network dependency tree" and LCP element |
| JavaScript up | a new library or a big module | `test_lighthouse.py` fails first; 100 KB is the limit, and there is no build step to shrink it |
| Performance down on the deployed run only | the live data is heavier, or GitHub Pages is slow that minute | run it again; the middle of three absorbs one bad run |
