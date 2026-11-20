"""Rewrite contracts/openapi.json from the app's real OpenAPI, built as freemocap/tests/test_api_contract.py builds it.

Run from the repository root: `uv run python packages/freemocap-client/tools/refresh-openapi.py`, then `npm run generate`.
Existing key order and existing `example`/`examples` values are kept (regenerated examples carry a user path and a timestamp);
new keys are appended and keys the app no longer has are dropped.
"""
import json
from pathlib import Path

from fastapi import FastAPI

import freemocap.app.app as app_module
from freemocap.app.app import _customize_openapi, _register_routes

TARGET = Path(__file__).resolve().parent.parent / "contracts" / "openapi.json"


def merge(old, new, key=None):
    if key in ("example", "examples"):
        return old
    if isinstance(old, dict) and isinstance(new, dict):
        merged = {k: merge(old[k], new[k], k) for k in old if k in new}
        merged.update({k: v for k, v in new.items() if k not in old})
        return merged
    return new


app_module.logger.api = lambda *args, **kwargs: None
app = FastAPI()
_register_routes(app)
_customize_openapi(app)
schema = app.openapi()
if TARGET.exists():
    existing = json.loads(TARGET.read_text(encoding="utf-8"))
    for key in existing.keys() & schema.keys():
        schema[key] = merge(existing[key], schema[key], key)
    schema = {**{k: schema[k] for k in existing if k in schema}, **{k: v for k, v in schema.items() if k not in existing}}
TARGET.write_text(json.dumps(schema, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
