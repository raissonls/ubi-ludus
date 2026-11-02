# Security policy

Ubi Ludus is a small, free, open-source project run by one maintainer. It has no accounts and collects no personal data: a visitor's choices stay in their own browser. Even so, if you find a problem, please tell us.

## Reporting a vulnerability

Please **do not open a public issue** for a security problem.

Use GitHub's private reporting instead: open the **Security** tab of this repository and choose **Report a vulnerability**. Only the maintainer sees the report. This option is available once the repository is public.

Include what you found, how to reproduce it, and what you think the impact is. A link or a short description is enough; you don't need a fix.

## What is in scope

- A secret, key or token committed to the repository or visible in a workflow log.
- A way to run script in a visitor's browser through the site (cross-site scripting), or to make the site load content from somewhere unexpected.
- A way for the site, the e-mail or the pipeline to collect or leak personal data.
- A weakness in the GitHub Actions workflows, for example excess permissions.

## What is not a security problem

- **Wrong broadcaster or kickoff information.** Please open a normal issue with the match, the date and a link to the official source. This is the most useful report you can send.
- Missing data for a competition. Some competitions are listed as "not covered yet" on purpose.

## What to expect

This is a one-person project, so replies are best effort, usually within a week. I will confirm the report, fix it when it is real, and credit you if you want to be credited.

## Supported versions

The project is in its first phase and only the latest version on the `main` branch is supported.
