#!/usr/bin/env python3
"""Apply the organization's CI rulesets and custom property, or check them for drift.

    scripts/apply_rulesets.py --check   # exit 1 when GitHub differs from rulesets/
    scripts/apply_rulesets.py           # create or update to match rulesets/

- rulesets/ci-tier-property.json: the `ci-tier` custom property.
- rulesets/org/*.json: organization rulesets.
- rulesets/repo/*.json: repository rulesets, put on every repository whose
  `ci-tier` is `merge-queue`. GitHub doesn't accept a merge-queue rule in an
  organization ruleset, so the queue lives here.
- rulesets/repo-settings.json: the merge settings of those repositories:
  squash for the queue, merge commits for a pull request that must keep its
  merge commit, no rebase.

Needs the `gh` CLI signed in as an organization owner with the admin:org scope
(`gh auth refresh -h github.com -s admin:org`). Org-setting changes follow the
Change Management Policy: announce them when made. A repository that leaves
the queue (its property unset) keeps its `merge-queue` ruleset until someone
deletes it: `gh api -X DELETE repos/<owner>/<name>/rulesets/<id>`.
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
SETTINGS_FILE = ROOT / "repo-settings.json"
OPT_IN_VALUE = "merge-queue"


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


def gh_list(endpoint: str) -> list[Any]:
    # `--slurp` wraps the pages in one array; `--paginate` alone prints one
    # JSON array per page, which is not one JSON document.
    return [item for page in gh(endpoint, "--paginate", "--slurp") for item in page]


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


def opted_in(property_values: list[dict[str, Any]], property_name: str) -> list[str]:
    """The repositories whose `property_name` is the opt-in value."""
    return sorted(
        repo["repository_name"]
        for repo in property_values
        if any(p["property_name"] == property_name and p["value"] == OPT_IN_VALUE for p in repo["properties"])
    )


def sync_property(org: str, want: dict[str, Any], check: bool) -> bool:
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


def sync_ruleset(scope: str, want: dict[str, Any], check: bool) -> bool:
    """Make the ruleset named `want["name"]` under `scope` (orgs/<org> or repos/<owner>/<name>) match `want`."""
    label = f"{scope} ruleset {want['name']}"
    # A repository's list includes the organization's rulesets unless told not to.
    listing = f"{scope}/rulesets" + ("?includes_parents=false" if scope.startswith("repos/") else "")
    existing = {r["name"]: r["id"] for r in gh_list(listing)}
    if want["name"] in existing:
        found = differences(want, gh(f"{scope}/rulesets/{existing[want['name']]}"))
        if not found:
            print(f"{label}: up to date")
            return True
        print(f"{label}: " + "; ".join(found))
        if check:
            return False
        gh("-X", "PUT", f"{scope}/rulesets/{existing[want['name']]}", payload=want)
    else:
        print(f"{label}: missing")
        if check:
            return False
        gh("-X", "POST", f"{scope}/rulesets", payload=want)
    print(f"{label}: applied")
    return True


def sync_settings(repo: str, want: dict[str, Any], check: bool) -> bool:
    """Make the settings of `repo` (repos/<owner>/<name>) that `want` names match it."""
    label = f"{repo} settings"
    found = differences(want, gh(repo))
    if not found:
        print(f"{label}: up to date")
        return True
    print(f"{label}: " + "; ".join(found))
    if check:
        return False
    gh("-X", "PATCH", repo, payload=want)
    print(f"{label}: applied")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--org", default="cocoindex-io")
    parser.add_argument("--check", action="store_true", help="report drift and exit 1 instead of applying")
    args = parser.parse_args()
    prop = json.loads(PROPERTY_FILE.read_text())
    # The property comes first: the organization ruleset's condition names it.
    ok = sync_property(args.org, prop, args.check)
    for path in sorted((ROOT / "org").glob("*.json")):
        ok = sync_ruleset(f"orgs/{args.org}", json.loads(path.read_text()), args.check) and ok
    repos = opted_in(gh_list(f"orgs/{args.org}/properties/values"), prop["property_name"])
    print(f"repositories with {prop['property_name']}={OPT_IN_VALUE}: {', '.join(repos) or 'none'}")
    settings = json.loads(SETTINGS_FILE.read_text())
    # A merge-queue rule may only name a merge method the repository allows,
    # so methods are enabled before the rulesets and disabled after them.
    enabling = {key: value for key, value in settings.items() if key.startswith("allow_") and value is True}
    for repo in repos:
        scope = f"repos/{args.org}/{repo}"
        if not args.check:
            ok = sync_settings(scope, enabling, check=False) and ok
        for path in sorted((ROOT / "repo").glob("*.json")):
            ok = sync_ruleset(scope, json.loads(path.read_text()), args.check) and ok
        ok = sync_settings(scope, settings, args.check) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
