# Architecture decision records

Short notes that explain **why** a meaningful technical choice was made, so nobody has to guess later. Write one when a decision is hard to reverse, affects several parts of the project, or will surprise a newcomer.

**How to add one**

1. Copy [template.md](template.md) to `ADR-NNN-short-title.md`, using the next number.
2. Fill it in, keeping it to about one page.
3. Add it to the table below and open a pull request.
4. An accepted ADR is not edited to change history. To change a decision, write a new ADR and mark the old one "Superseded by ADR-NNN".

| ADR | Title | Status |
|---|---|---|
| [ADR-001](ADR-001-architecture.md) | Static pipeline architecture and data providers | Accepted |
| [ADR-002](ADR-002-dbt-duckdb.md) | dbt and Python together, on DuckDB | Accepted |
