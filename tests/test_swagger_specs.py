#!/usr/bin/env python3
"""The rendered OpenAPI spec is well-formed.

Specs are hand-edited YAML with inconsistent indentation between files,
and one mis-indented insertion nested a 200 response inside a 400 in
swag/putnewaccount.yaml. Nothing noticed: flasgger catches the TypeError
Flask's sorted jsonify raises on mixed int/str keys, falls back to
json.dumps, and still serves HTTP 200 — so /apidocs looked fine while
documenting a response that did not exist. These checks make that loud.

Run with: pytest tests/test_swagger_specs.py -v
"""

import gc
import json

import pytest


@pytest.fixture(scope="module")
def spec(pbrest):
    import flasgger

    sw = next(o for o in gc.get_objects() if isinstance(o, flasgger.Swagger))
    with pbrest.app.test_request_context():
        return sw.get_apispecs("apispec_1")


def _operations(spec):
    for path, methods in spec["paths"].items():
        for method, op in methods.items():
            if isinstance(op, dict) and "responses" in op:
                yield f"{method.upper()} {path}", op


def test_spec_serialises_with_sorted_keys(spec):
    """What Flask's jsonify does. Mixed key types in any dict fail here,
    which is the error flasgger was silently swallowing."""
    json.dumps(spec, sort_keys=True)


def test_every_dict_key_is_a_string(spec):
    bad = []

    def walk(o, where):
        if isinstance(o, dict):
            nonstr = [k for k in o if not isinstance(k, str)]
            if nonstr:
                bad.append(f"{where}: {nonstr}")
            for k, v in o.items():
                walk(v, f"{where}/{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{where}[{i}]")

    walk(spec, "")
    assert not bad, "non-string keys (usually a mis-indented response code):\n" + "\n".join(bad)


def test_no_response_nested_inside_another(spec):
    """A status code must never appear as a key inside another response."""
    bad = []
    for name, op in _operations(spec):
        for code, resp in op["responses"].items():
            if not isinstance(resp, dict):
                continue
            nested = [k for k in resp if str(k).isdigit() and len(str(k)) == 3]
            if nested:
                bad.append(f"{name}: response {code} contains {nested}")
    assert not bad, "\n".join(bad)


def test_every_operation_documents_success_and_failure(spec):
    missing = []
    for name, op in _operations(spec):
        codes = {str(c) for c in op["responses"]}
        if not any(c.startswith("2") for c in codes):
            missing.append(f"{name}: no 2xx")
        if "500" not in codes:
            missing.append(f"{name}: no 500")
    assert not missing, "\n".join(missing)


def test_error_schemas_include_status(spec):
    """handle_error always emits status; every documented 500 must say so."""
    bad = [name for name, op in _operations(spec)
           if "status" not in ((op["responses"].get("500") or {}).get("schema") or {}).get("properties", {})]
    assert not bad, "500 schema missing 'status':\n" + "\n".join(bad)
