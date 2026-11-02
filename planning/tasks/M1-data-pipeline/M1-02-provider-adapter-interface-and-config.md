---
id: M1-02
title: Provider adapter interface and config
milestone: M1
priority: Must
estimate_h: 3
status: todo
requirements: [FR-01]
depends_on: [M1-01]
---

# M1-02 · Provider adapter interface and config

**Milestone:** M1 Data pipeline (Nov 9-15) · **Priority:** Must · **Estimate:** 3 h

## Why

Adding a provider must only need a new adapter module and a config entry.

## Definition of done

- [ ] Abstract adapter interface in `src/pipeline/providers/` with the methods the pipeline needs.
- [ ] `config/competitions.yml` mapping our competitions to provider IDs.
- [ ] Adapter registry that picks adapters from config.
- [ ] A fake adapter proves the interface works in tests.

## Notes

_Add decisions, links and anything learned while doing the task._
