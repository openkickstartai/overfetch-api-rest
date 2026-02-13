"""Tests for OverFetch analyzer — 7 test cases covering core functionality."""
import json, os, tempfile
from pathlib import Path
from analyzer import parse_openapi, analyze_source, compute_report, normalize, scan_dir

SPEC = {"openapi": "3.0.0", "info": {"title": "T", "version": "1"},
    "paths": {"/api/users": {"get": {"responses": {"200": {"content": {"application/json": {
        "schema": {"type": "object", "properties": {
            "id": {"type": "integer"}, "name": {"type": "string"},
            "email": {"type": "string"}, "avatar": {"type": "string"},
            "created_at": {"type": "string"}, "role": {"type": "string"},
            "bio": {"type": "string"}, "phone": {"type": "string"}}}}}}}}}}},
    "components": {"schemas": {}}}

def _spec_file(tmp):
    p = os.path.join(tmp, "spec.json")
    Path(p).write_text(json.dumps(SPEC))
    return p

def test_parse_openapi_extracts_all_fields():
    with tempfile.TemporaryDirectory() as tmp:
        fields = parse_openapi(_spec_file(tmp))
        assert "GET /api/users" in fields
        assert fields["GET /api/users"] == {"id","name","email","avatar","created_at","role","bio","phone"}

def test_analyze_destructuring_pattern():
    code = "const resp = await fetch('/api/users');\nconst { name, email } = await resp.json();"
    r = analyze_source(code)
    assert "/api/users" in r
    assert r["/api/users"] >= {"name", "email"}

def test_analyze_property_access_pattern():
    code = "const d = await axios.get('/api/users');\nconsole.log(data.name, data.avatar);"
    r = analyze_source(code)
    assert "/api/users" in r
    assert "name" in r["/api/users"] and "avatar" in r["/api/users"]

def test_compute_report_utilization():
    spec = {"GET /api/users": {"id","name","email","avatar","bio","phone","role","created_at"}}
    used = {"/api/users": {"name", "email"}}
    report = compute_report(spec, used)
    assert report["overall_pct"] == 25.0
    ep = report["endpoints"][0]
    assert ep["used_fields"] == 2 and ep["total_fields"] == 8
    assert any("CRITICAL" in r for r in report["recommendations"])

def test_normalize_urls():
    assert normalize("https://api.example.com/users/123") == "/users/{id}"
    assert normalize("/api/items/${itemId}") == "/api/items/{id}"
    assert normalize("/api/data?page=1&size=20") == "/api/data"
    assert normalize("/api/users/:userId/posts") == "/api/users/{id}/posts"

def test_multiple_endpoints_strategic_recommendation():
    spec = {"GET /a": set(f"f{i}" for i in range(10)),
            "GET /b": set(f"x{i}" for i in range(5))}
    used = {"/a": {"f1"}, "/b": {"x1"}}
    r = compute_report(spec, used)
    assert r["overall_pct"] == round(2 / 15 * 100, 1)
    assert sum(1 for x in r["recommendations"] if "CRITICAL" in x) >= 2
    assert any("STRATEGIC" in x for x in r["recommendations"])

def test_ref_schema_resolution():
    spec = {"openapi": "3.0.0", "info": {"title": "T", "version": "1"},
        "paths": {"/items": {"get": {"responses": {"200": {"content": {"application/json": {
            "schema": {"$ref": "#/components/schemas/Item"}}}}}}}}},
        "components": {"schemas": {"Item": {"type": "object",
            "properties": {"id": {"type": "integer"}, "title": {"type": "string"}}}}}}
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "s.json")
        Path(p).write_text(json.dumps(spec))
        fields = parse_openapi(p)
        assert fields["GET /items"] == {"id", "title"}

def test_scan_dir_with_ts_files():
    with tempfile.TemporaryDirectory() as tmp:
        ts_file = Path(tmp) / "app.ts"
        ts_file.write_text("const r = await fetch('/api/products');\nconst { price } = r;")
        result = scan_dir(tmp)
        assert "/api/products" in result
        assert "price" in result["/api/products"]

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
