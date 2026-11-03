# Privacy

Ubi Ludus shows where to watch football in Brazil. It is built so that it does not need to know anything about you.

## What the site does not do

- **No accounts, no sign-up, no cookies.**
- **No analytics and no trackers** that identify people. If aggregate, cookieless statistics are ever added, this page will say so first.
- **No third-party requests.** The site loads everything (scripts, styles, fonts, the data) from its own address. Nothing is fetched from an advertising, analytics or font service, and a Content Security Policy in every page stops it from happening by mistake.

## What stays in your browser

The teams you follow and the services you have are saved **only in your browser** (`localStorage`) so the site remembers them the next time. They are never sent anywhere. You can change or clear them at any time with the "reset my data" control, or by clearing the site's data in your browser. The sharing links that carry your choices in the address (a later feature) contain team and service ids only, never anything personal.

## What others can see

- **GitHub** hosts the site (GitHub Pages). Like any web host, GitHub receives your IP address and the usual request details when you open a page, and handles them under [its own privacy statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement). This project does not receive or read those logs.
- **The project's repository is public**, including the data files the site publishes (matches, teams, competitions, broadcasters). None of it is about visitors.
- **The daily e-mail** is for the owner of the project only. Its address is stored as a repository secret, never in the code. Visitors are never e-mailed.

## Data from other sources

Match data comes from [football-data.org](https://www.football-data.org/) and [API-Football](https://www.api-football.com/). The site shows only what it needs (team names, competition, kickoff time, status and where it is shown). Team crests and logos are not used.

## Brazil's LGPD

Because the site collects no personal data about visitors, there is nothing to access, correct or delete on our side. If you think the site handles personal data it should not, [open an issue](https://github.com/raissonls/ubi-ludus/issues) and it will be fixed.

_Last updated: 2026-11-03._
