#!/usr/bin/env python3
"""Apply the organization's CI rulesets and custom property, or check them for drift.

    scripts/apply_rulesets.py --check   # exit 1 when GitHub differs from rulesets/
    scripts/apply_rulesets.py           # create or update to match rulesets/

Needs the `gh` CLI signed in as an organization owner with the admin:org scope
(`gh auth refresh -h github.com -s admin:org`). Org-setting changes follow the
Change Management Policy: announce them when made.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent.parent / "rulesets"
PROPERTY_FILE = ROOT / "ci-tier-property.json"


def gh(*args: str, payload: dict[str, Any] | None = None) -> Any:
    command = ["gh", "api", *args]
    if payload is not None:
        command += ["--input", "-"]
    result = subprocess.run(
        command, input=json.dumps(payload) if payload is not None else None,
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.exit(f"gh api {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}")
    return json.loads(result.stdout) if result.stdout.strip() else None


def differences(want: Any, have: Any, where: str = "") -> list[str]:
    """List where `have` differs from `want`, ignoring keys `want` doesn't set."""
    if isinstance(want, dict):
        if not isinstance(have, dict):
            return [f"{where or '.'}: expected an object"]
        return [d for key, value in want.items() for d in differences(value, have.get(key), f"{where}.{key}")]
    if isinstance(want, list):
        if not isinstance(have, list) or len(want) != len(have):
            return [f"{where}: expected {json.dumps(want)}, found {json.dumps(have)}"]
        if want and isinstance(want[0], dict) and "type" in want[0]:
            by_type = {item.get("type"): item for item in have}
            return [d for item in want for d in differences(item, by_type.get(item["type"]), f"{where}[{item['type']}]")]
        return [d for i, (w, h) in enumerate(zip(want, have)) for d in differences(w, h, f"{where}[{i}]")]
    return [] if want == have else [f"{where}: expected {json.dumps(want)}, found {json.dumps(have)}"]


def sync_property(org: str, check: bool) -> bool:
    want = json.loads(PROPERTY_FILE.read_text())
    have = {p["property_name"]: p for p in gh(f"orgs/{org}/properties/schema")}.get(want["property_name"])
    found = differences(want, have) if have else ["missing"]
    if not found:
        print(f"property {want['property_name']}: up to date")
        return True
    print(f"property {want['property_name']}: " + "; ".join(found))
    if check:
        return False
    gh("-X", "PUT", f"orgs/{org}/properties/schema/{want['property_name']}",
       payload={k: v for k, v in want.items() if k != "property_name"})
    print(f"property {want['property_name']}: applied")
    return True


def sync_ruleset(org: str, path: pathlib.Path, check: bool) -> bool:
    want = json.loads(path.read_text())
    # `--slurp` wraps the pages in one array; `--paginate` alone prints one
    # JSON array per page, which is not one JSON document.
    pages = gh(f"orgs/{org}/rulesets", "--paginate", "--slurp")
    existing = {r["name"]: r["id"] for page in pages for r in page}
    if want["name"] in existing:
        have = gh(f"orgs/{org}/rulesets/{existing[want['name']]}")
        found = differences(want, have)
        if not found:
            print(f"ruleset {want['name']}: up to date")
            return True
        print(f"ruleset {want['name']}: " + "; ".join(found))
        if check:
            return False
        gh("-X", "PUT", f"orgs/{org}/rulesets/{existing[want['name']]}", payload=want)
    else:
        print(f"ruleset {want['name']}: missing")
        if check:
            return False
        gh("-X", "POST", f"orgs/{org}/rulesets", payload=want)
    print(f"ruleset {want['name']}: applied")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--org", default="cocoindex-io")
    parser.add_argument("--check", action="store_true", help="report drift and exit 1 instead of applying")
    args = parser.parse_args()
    # The property comes first: a ruleset's repository_property condition names it.
    ok = sync_property(args.org, args.check)
    for path in sorted(ROOT.glob("*.json")):
        if path != PROPERTY_FILE:
            ok = sync_ruleset(args.org, path, args.check) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
