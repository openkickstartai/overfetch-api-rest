"""OverFetch core: OpenAPI parsing and JS/TS field-usage static analysis."""
import re, json
from pathlib import Path
from typing import Dict, Set

def parse_openapi(spec_path: str) -> Dict[str, Set[str]]:
    path = Path(spec_path)
    if not path.exists():
        raise FileNotFoundError(f"Spec not found: {spec_path}")
    raw = path.read_text(encoding="utf-8")
    if path.suffix in (".yml", ".yaml"):
        import yaml
        spec = yaml.safe_load(raw)
    else:
        spec = json.loads(raw)
    result, schemas = {}, spec.get("components", {}).get("schemas", {})
    for p, methods in spec.get("paths", {}).items():
        for m, op in methods.items():
            if m not in ("get", "post", "put", "patch", "delete"):
                continue
            fields = _response_fields(op, schemas)
            if fields:
                result[f"{m.upper()} {p}"] = fields
    return result

def _resolve(s, schemas):
    return schemas.get(s["$ref"].split("/")[-1], {}) if "$ref" in s else s

def _response_fields(op, schemas):
    fields = set()
    for code, resp in op.get("responses", {}).items():
        if not str(code).startswith("2"):
            continue
        s = _resolve(resp.get("content", {}).get("application/json", {}).get("schema", {}), schemas)
        if s.get("type") == "array" and "items" in s:
            s = _resolve(s["items"], schemas)
        fields.update(s.get("properties", {}).keys())
    return fields

_SKIP = {"json","data","then","catch","status","ok","headers","body","text","length"}
_API_RE = re.compile(
    r'(?:fetch|axios\.(?:get|post|put|patch|delete)|'
    r'api\.(?:get|post|put|patch|delete))\s*\(\s*[\'"`]([^\'"`]+)[\'"`]')
_DESTR_RE = re.compile(r'(?:const|let|var)\s*\{([^}]+)\}\s*=')
_PROP_RE = re.compile(r'(?:response|data|result|res|body)\.(\w+)')

def analyze_source(content: str) -> Dict[str, Set[str]]:
    endpoints, used = _API_RE.findall(content), set()
    for m in _DESTR_RE.finditer(content):
        for f in m.group(1).split(","):
            name = f.strip().split(":")[0].split("=")[0].strip()
            if name:
                used.add(name)
    for m in _PROP_RE.finditer(content):
        if m.group(1) not in _SKIP:
            used.add(m.group(1))
    result = {}
    for ep in endpoints:
        result.setdefault(normalize(ep), set()).update(used)
    return result

def normalize(url: str) -> str:
    url = re.sub(r"^https?://[^/]+", "", url.split("?")[0])
    url = re.sub(r"/\d+", "/{id}", url)
    url = re.sub(r"/:[^/]+", "/{id}", url)
    return re.sub(r"/\$\{[^}]+\}", "/{id}", url)

def scan_dir(src: str) -> Dict[str, Set[str]]:
    combined: Dict[str, Set[str]] = {}
    exts = (".js", ".jsx", ".ts", ".tsx")
    for p in Path(src).rglob("*"):
        if p.suffix in exts and "node_modules" not in p.parts:
            for ep, flds in analyze_source(p.read_text(errors="ignore")).items():
                combined.setdefault(ep, set()).update(flds)
    return combined

def match_ep(spec_ep: str, code_ep: str) -> bool:
    sp = spec_ep.split(" ", 1)[-1] if " " in spec_ep else spec_ep
    n = lambda s: re.sub(r"\{[^}]+\}", "{id}", s)
    return n(sp) == n(code_ep)

def compute_report(spec_f, used_f, avg_bytes=2048):
    eps, ts, tu = [], 0, 0
    for endpoint, af in spec_f.items():
        matched = set()
        for ue, uf in used_f.items():
            if match_ep(endpoint, ue):
                matched.update(uf)
        actual = matched & af
        pct = round(len(actual) / len(af) * 100, 1) if af else 100.0
        ts += len(af)
        tu += len(actual)
        w = 1 - len(actual) / len(af) if af else 0
        eps.append({"endpoint": endpoint, "total_fields": len(af),
            "used_fields": len(actual), "utilization_pct": pct,
            "unused": sorted(af - actual), "used": sorted(actual),
            "waste_bytes_per_call": int(avg_bytes * w)})
    eps.sort(key=lambda x: x["utilization_pct"])
    recs = []
    for e in eps:
        if e["utilization_pct"] < 30:
            recs.append(f"CRITICAL: {e['endpoint']} \u2014 {e['utilization_pct']}% field utilization.")
        elif e["utilization_pct"] < 60:
            recs.append(f"WARNING: {e['endpoint']} \u2014 {e['utilization_pct']}% field utilization.")
    if len(eps) >= 2 and sum(1 for e in eps if e["utilization_pct"] < 50) > len(eps) * 0.5:
        recs.append("STRATEGIC: Majority of endpoints underutilized. Evaluate GraphQL/BFF.")
    return {"overall_pct": round(tu / ts * 100, 1) if ts else 100.0,
            "endpoints": eps, "recommendations": recs}
