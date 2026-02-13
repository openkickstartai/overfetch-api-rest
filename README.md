# OverFetch

> Quantify REST API over-fetching — know exactly how many response fields your frontend actually uses.

REST endpoints return 40 fields, your frontend uses 7. OverFetch gives you **data, not guesses**.

## Install

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Text report
python overfetch.py --spec openapi.json --src ./src

# JSON output with CI threshold
python overfetch.py --spec openapi.yaml --src ./src --format json --threshold 30

# Custom avg response size for bandwidth estimation
python overfetch.py --spec api.json --src ./frontend -o report.txt --avg-bytes 4096
```

## How It Works

1. **Parses your OpenAPI 3.x spec** — extracts every response field per endpoint (with `$ref` resolution)
2. **Scans frontend JS/TS code** — detects `fetch`/`axios`/`api.*` calls, tracks destructuring (`const { name } = ...`) and property access (`data.name`)
3. **Compares** spec fields vs. used fields → utilization percentage per endpoint
4. **Generates recommendations** — CRITICAL (<30%), WARNING (<60%), STRATEGIC (GraphQL/BFF migration signal)

## CI Integration

```yaml
- run: python overfetch.py --spec openapi.json --src ./src --threshold 30
```

Exits with code 1 if any endpoint utilization falls below the threshold.

## Output Example

```
  OverFetch Report — Overall: 25.0% utilization

  GET /api/users
    [█████░░░░░░░░░░░░░░░] 25.0%  (2/8 fields)
    Unused: avatar, bio, created_at, phone, role
    Est. waste: ~1536 bytes/call

  • CRITICAL: GET /api/users — 25.0% field utilization.
```

## License

MIT
