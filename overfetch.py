#!/usr/bin/env python3
"""OverFetch CLI \u2014 Quantify REST API over-fetching in your frontend codebase."""
import argparse, json, sys
from analyzer import parse_openapi, scan_dir, compute_report


def main():
    p = argparse.ArgumentParser(prog="overfetch",
        description="Quantify REST API over-fetching by analyzing frontend field usage")
    p.add_argument("--spec", required=True, help="OpenAPI spec path (JSON/YAML)")
    p.add_argument("--src", required=True, help="Frontend source directory to scan")
    p.add_argument("--avg-bytes", type=int, default=2048, help="Avg response size in bytes")
    p.add_argument("--threshold", type=float, default=0,
        help="Min utilization pct; exit 1 if any endpoint below this")
    p.add_argument("--format", choices=["json", "text"], default="text")
    p.add_argument("-o", "--output", help="Write report to file instead of stdout")
    args = p.parse_args()
    try:
        spec_fields = parse_openapi(args.spec)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    if not spec_fields:
        print("No endpoints found in spec.", file=sys.stderr)
        sys.exit(1)
    used_fields = scan_dir(args.src)
    report = compute_report(spec_fields, used_fields, args.avg_bytes)
    out = json.dumps(report, indent=2) if args.format == "json" else format_text(report)
    if args.output:
        with open(args.output, "w") as f:
            f.write(out + "\n")
        print(f"Report written to {args.output}")
    else:
        print(out)
    if args.threshold > 0:
        bad = [e for e in report["endpoints"] if e["utilization_pct"] < args.threshold]
        if bad:
            names = ", ".join(e["endpoint"] for e in bad)
            print(f"\n\u2717 {len(bad)} endpoint(s) below {args.threshold}% threshold: {names}",
                  file=sys.stderr)
            sys.exit(1)


def format_text(report):
    lines = ["", "\u2550" * 42,
             f"  OverFetch Report \u2014 Overall: {report['overall_pct']}% utilization",
             "\u2550" * 42, ""]
    for ep in report["endpoints"]:
        filled = int(ep["utilization_pct"] / 5)
        bar = "\u2588" * filled + "\u2591" * (20 - filled)
        lines.append(f"  {ep['endpoint']}")
        lines.append(f"    [{bar}] {ep['utilization_pct']}%  ({ep['used_fields']}/{ep['total_fields']} fields)")
        if ep["unused"]:
            lines.append(f"    Unused: {', '.join(ep['unused'][:6])}")
        lines.append(f"    Est. waste: ~{ep['waste_bytes_per_call']} bytes/call")
        lines.append("")
    if report["recommendations"]:
        lines.append("\u2500\u2500 Recommendations \u2500\u2500")
        for r in report["recommendations"]:
            lines.append(f"  \u2022 {r}")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
