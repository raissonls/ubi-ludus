---
id: M4-02
title: E-mail sending, secrets and skip logic
milestone: M4
priority: Must
estimate_h: 3
status: todo
requirements: [FR-40, FR-41, FR-42, Q3]
depends_on: [M4-01]
---

# M4-02 · E-mail sending, secrets and skip logic

**Milestone:** M4 E-mail and operations (Dec 7-13) · **Priority:** Must · **Estimate:** 3 h

## Why

Actually send it, without ever putting the address or credentials in the repo. Decision on Q3 (sending method) is needed at the start of M4.

## Definition of done

- [ ] Open question Q3 answered and the sending method documented.
- [ ] Address and credentials live only in GitHub Secrets; a missing secret fails the job with a clear message.
- [ ] Configurable flag: skip the e-mail on days without relevant matches, or send a short "no matches today" note; both tested.
- [ ] Secret scanning finds nothing in the repo or logs.

## Notes

_Add decisions, links and anything learned while doing the task._
