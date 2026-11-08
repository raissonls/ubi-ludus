# Privacy

Ubi Ludus shows where to watch football in Brazil. It is built so that it does not need to know anything about you.

## What the site does not do

- **No accounts, no sign-up, no cookies.**
- **No analytics and no trackers** that identify people. If aggregate, cookieless statistics are ever added, this page will say so first.
- **No third-party requests.** The site loads everything (scripts, styles, fonts, the data) from its own address. Nothing is fetched from an advertising, analytics or font service, and a Content Security Policy in every page stops it from happening by mistake.

## What stays in your browser

The teams you follow, the services you have and whether you hide the matches you cannot watch are saved **only in your browser** (`localStorage`) so the site remembers them the next time. They are never sent anywhere. The site also remembers, with a single marker in `localStorage`, that you have already seen the first-run screens (the welcome and the choice of continent, country and team), so it does not show them again; it holds nothing else. You can change or clear them at any time with the "reset my data" control, or by clearing the site's data in your browser. Your choices are in the address only if you press "Copiar link desta visão" to share a view; that link contains team and service ids, never anything personal, and opening it saves nothing on the other person's device. The filters you set (competition, broadcaster, a team's name) are in the address of the page you are on, so a bookmark keeps them; they are not sent anywhere either.

## What others can see

- **GitHub** hosts the site (GitHub Pages). Like any web host, GitHub receives your IP address and the usual request details when you open a page, and handles them under [its own privacy statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement). This project does not receive or read those logs.
- **The "report a wrong broadcast" links** open a new issue on the project's GitHub repository, with the match and the broadcasters the site showed already filled in. Nothing about you is in the link (not your teams or services), and nothing happens until you click it. What you then write on GitHub is public and governed by GitHub's terms and your GitHub account.
- **"Add to calendar" files** are written in your browser from the match data and saved by your browser like any download. Nothing is sent anywhere to make them, and they do not say which teams you follow.
- **A copy of the match data** (the same files the site publishes, nothing about you) is kept in your browser's cache storage after each successful load, so the site can still show the matches the last time it loaded when the connection fails. Clearing the site's data in your browser removes it.
- **The project's repository is public**, including the data files the site publishes (matches, teams, competitions, broadcasters). None of it is about visitors.
- **The daily e-mail** is for the owner of the project only. Its address is stored as a repository secret, never in the code. Visitors are never e-mailed.

## Data from other sources

Match data comes from [football-data.org](https://www.football-data.org/). The site shows only what it needs (team names, competition, kickoff time, status and where it is shown). Team crests and logos are not used.

## Brazil's LGPD

Because the site collects no personal data about visitors, there is nothing to access, correct or delete on our side. If you think the site handles personal data it should not, [open an issue](https://github.com/raissonls/ubi-ludus/issues) and it will be fixed.

_Last updated: 2026-11-03._
