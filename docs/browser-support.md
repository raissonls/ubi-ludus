# Browser support

Which browsers Ubi Ludus promises to work in, why, and what is tested. Most visitors are on a phone,
so the iPhone and Android rows matter most. A bug in a browser listed here is a bug; a problem in an
older one is not, but it should never leave the visitor with a blank page.

A unit test (`tests/unit/test_browser_support.py`) reads this file. It fails if the site starts
using a feature that is not in the second table, if a feature needs a newer browser than the first
table promises, or if the tables and the test runs drift apart.

## What we support

The floor is the oldest version each browser needs for everything the site uses today. Newer
versions are supported too. Versions are the engine's version, which is what the table of features
below uses.

| Browser | From version | Why |
|---|---|---|
| Safari on iOS and iPadOS | 16.4 | `color-mix()` needs 16.2 and the dialog features need 15.5; 16.4 is the round number above both |
| Safari on macOS | 16.4 | Same engine as above |
| Chrome on Android | 111 | `color-mix()` |
| Chrome on desktop | 111 | Same |
| Edge | 111 | Same engine as Chrome |
| Firefox (desktop and Android) | 121 | `:has()` |

Not promised: Internet Explorer, Opera Mini, UC Browser, and browsers more than two years behind.
Samsung Internet and other Chromium browsers follow the Chrome row.

## What the site uses

One row for each feature of the web platform the site relies on that is newer than the others.
The columns are the first version that has it (Chrome and Edge, Safari, Firefox). The detection is
in the unit test, by the name in the first column; add a row here and a detector there when a new
feature goes in.

| Feature | Chrome | Safari | Firefox | Used for |
|---|---|---|---|---|
| `dialog.showModal()` and `::backdrop` | 37 | 15.4 | 98 | The settings panel, the match sheet and the first-run flow |
| The `inert` attribute | 102 | 15.5 | 112 | Keeps the page behind a sheet out of reach of the keyboard and a screen reader |
| `dvh` units | 108 | 15.4 | 101 | The panel is as tall as the visible screen, with the phone's address bar in or out |
| `:has()` | 105 | 15.4 | 121 | The focus ring around a whole poster when its button has the keyboard focus |
| `color-mix()` | 111 | 16.2 | 113 | The wash of a team's colour on a poster, and the glow and pulse animations |
| `:focus-visible` | 86 | 15.4 | 85 | The focus ring appears for the keyboard, not for a tap |
| `Intl.ListFormat` | 72 | 14.1 | 78 | "Globo, SporTV e Premiere" in the right language |
| `Intl.PluralRules` | 63 | 13 | 58 | "1 time escolhido", "2 times escolhidos" |
| `replaceChildren()` | 86 | 14 | 78 | Drawing lists without leaving old rows behind |
| `overscroll-behavior` | 63 | 16 | 59 | The sheet does not scroll the page behind it |
| Scroll snapping | 69 | 11 | 68 | Rails of posters stop on a poster |
| `clipboard.writeText()` | 66 | 13.1 | 63 | Copy the link of a match |

## What happens on an older browser

The page is plain HTML first, and the scripts are ES modules, which every browser above the floor
reads. Below the floor:

- With JavaScript off, the page says so ("Este site precisa de JavaScript para mostrar os jogos").
  A browser too old to run the scripts at all gets the same HTML, without the lists.
- A style the browser does not know is dropped, and the rest of the page is not affected. For
  `color-mix()` that means no colour wash on a poster and no glow on the pulse animations; the
  text and buttons stay. For `:has()` it means no outline around the whole poster (the button
  still has its own focus ring).
- Nobody has checked these fallbacks on a real old browser, and no test does. Below the floor the
  promise is "it loads and the text is readable", not "it looks right".

## What is tested

| Run | Engine | Device | When |
|---|---|---|---|
| `chromium` | Chromium | A desktop and two phone-sized windows | Every pull request, all browser tests |
| `webkit-iphone` | WebKit | An iPhone: touch, 3x pixels, Safari's user agent | Every Monday and by hand |
| `chromium-android` | Chromium | An Android phone: touch, Chrome's user agent | Every Monday and by hand |

The weekly runs are in `.github/workflows/browser-matrix.yml`. How to run them on your own machine
and how to read a failure is in [the runbook](runbook.md#browser-matrix-webkit-and-phones).

Not tested: Firefox, any real device, any version below the floor, and Safari's own behaviour that
Playwright's WebKit does not reproduce (the on-screen keyboard resizing the page, the address bar
folding away). The screen-reader pass on an iPhone is by hand: see [the usability kit](usability/README.md).
