"""Validate pipeline output against the JSON Schemas in ``schemas/``.

Call :func:`validate` on anything the pipeline is about to publish. It raises
:class:`SchemaValidationError` on the first problem found, which fails the run, so
bad data never reaches the site (PRD FR-02).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError
from jsonschema.exceptions import best_match
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "schemas"
_SUFFIX = ".schema.json"
_MAX_REPORTED = 10


class SchemaValidationError(ValueError):
    """The document does not match its schema. ``errors`` lists every problem found."""

    def __init__(self, schema_name: str, errors: list[str]) -> None:
        self.schema_name = schema_name
        self.errors = errors
        shown = "\n".join(f"  - {line}" for line in errors[:_MAX_REPORTED])
        more = len(errors) - _MAX_REPORTED
        suffix = f"\n  ... and {more} more" if more > 0 else ""
        header = f"Invalid '{schema_name}' data ({len(errors)} problem(s)):"
        super().__init__(f"{header}\n{shown}{suffix}")


@lru_cache(maxsize=4)
def _load(schema_dir: Path) -> tuple[dict[str, dict[str, object]], Registry]:
    schemas: dict[str, dict[str, object]] = {}
    registry: Registry = Registry()
    for path in sorted(schema_dir.glob(f"*{_SUFFIX}")):
        contents = json.loads(path.read_text(encoding="utf-8"))
        schemas[path.name.removesuffix(_SUFFIX)] = contents
        resource = Resource.from_contents(contents, default_specification=DRAFT202012)
        registry = registry.with_resource(uri=str(contents["$id"]), resource=resource)
    return schemas, registry


def _explain(error: ValidationError) -> str:
    """For "nullable or X" fields, report why X failed instead of "not valid under any schema"."""
    not_null_branch = [
        c
        for c in error.context or []
        if not (c.validator == "type" and c.validator_value == "null")
    ]
    best = best_match(not_null_branch)
    return str(best.message if best is not None else error.message)


def schema_names(schema_dir: Path = SCHEMA_DIR) -> list[str]:
    """Names of the available schemas, for example ``matches`` or ``team``."""
    return sorted(_load(schema_dir)[0])


def validate(document: object, schema_name: str, *, schema_dir: Path = SCHEMA_DIR) -> None:
    """Raise :class:`SchemaValidationError` unless ``document`` matches ``schema_name``."""
    schemas, registry = _load(schema_dir)
    if schema_name not in schemas:
        raise KeyError(f"Unknown schema '{schema_name}'. Available: {', '.join(sorted(schemas))}")
    validator = Draft202012Validator(schemas[schema_name], registry=registry)
    found = validator.iter_errors(document)
    errors = sorted(found, key=lambda e: [str(p) for p in e.absolute_path])
    if errors:
        lines = [f"/{'/'.join(str(p) for p in e.absolute_path)}: {_explain(e)}" for e in errors]
        raise SchemaValidationError(schema_name, lines)


def validate_file(path: Path, schema_name: str, *, schema_dir: Path = SCHEMA_DIR) -> None:
    """Like :func:`validate`, for a JSON file on disk."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(schema_name, [f"{path.name} is not valid JSON: {exc}"]) from exc
    validate(document, schema_name, schema_dir=schema_dir)
