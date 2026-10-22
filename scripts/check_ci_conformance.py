#!/usr/bin/env python3
"""Check a repository's GitHub Actions workflows against the CocoIndex CI shape.

The shape is described in CI.md at the root of cocoindex-io/.github. Run it on a
checkout:

    uv run --with pyyaml scripts/check_ci_conformance.py PATH/TO/REPO

With --repo OWNER/NAME and the `gh` CLI signed in, it also checks that every
required status check of the default branch reports on merge-group runs.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
from typing import Any, NamedTuple

import yaml

CI_MODE_ACTION = "cocoindex-io/.github/actions/ci-mode@"
GATE_JOB = "ci-gate"
GITHUB_ACTIONS_APP_ID = 15368
# Status functions in a job's `if` replace the implicit success() check, so
# the job runs even when a job it needs was skipped.
STATUS_FUNCTIONS = ("always()", "cancelled()", "failure()")


class Finding(NamedTuple):
    path: str
    message: str


def _triggers(doc: dict[Any, Any]) -> dict[str, Any]:
    # YAML 1.1 reads a bare `on` key as the boolean True.
    on = doc.get("on", doc.get(True))
    if isinstance(on, str):
        return {on: None}
    if isinstance(on, list):
        return {name: None for name in on}
    return on or {}


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _grants_checks_read(permissions: Any) -> bool:
    if permissions in ("read-all", "write-all"):
        return True
    return isinstance(permissions, dict) and permissions.get("checks") in ("read", "write")


def check_workflow(path: str, doc: dict[Any, Any]) -> list[Finding]:
    findings: list[Finding] = []

    def fail(message: str) -> None:
        findings.append(Finding(path, message))

    on = _triggers(doc)
    jobs: dict[str, Any] = doc.get("jobs") or {}
    has_gate = GATE_JOB in jobs

    if "pull_request" in on:
        pull_request = on.get("pull_request") or {}
        types = pull_request.get("types") or []
        if "ready_for_review" not in types:
            fail("pull_request.types must list ready_for_review, or a draft marked ready never runs CI.")
        branch_filtered = "branches" in pull_request or "branches-ignore" in pull_request
        if (has_gate or branch_filtered) and "stacked" not in types:
            fail("pull_request.types must list stacked: a stack layer whose opened event arrives before its "
                 "stack exists misses the branch filter and runs no CI.")
        concurrency = doc.get("concurrency") or {}
        if isinstance(concurrency, str):  # `concurrency: <group>` is the short form
            concurrency = {"group": concurrency}
        group = _text(concurrency.get("group"))
        cancel = concurrency.get("cancel-in-progress")
        if "pull_request.number" not in group or cancel in (None, False):
            fail("A workflow-level concurrency group keyed on github.event.pull_request.number, "
                 "with cancel-in-progress, must cancel a pull request's superseded runs.")
        for job_id, job in jobs.items():
            condition = _text(job.get("if"))
            # A job that needs a skipped job is skipped too, unless a status
            # function in its `if` overrides the implicit success() check.
            inherits_skip = bool(job.get("needs")) and not any(f in condition for f in STATUS_FUNCTIONS)
            if "pull_request.draft" not in condition and not inherits_skip:
                fail(f"Job {job_id} must skip drafts: add `github.event.pull_request.draft != true` to its if.")

    if has_gate:
        if "merge_group" not in on:
            fail(f"The workflow with {GATE_JOB} must trigger on merge_group, or the merge queue waits forever.")
        gate = jobs[GATE_JOB]
        if "always()" not in _text(gate.get("if")):
            fail(f"{GATE_JOB} must run with if: always(), or a failed job leaves it skipped, which counts as a pass.")
        if not gate.get("needs"):
            fail(f"{GATE_JOB} must need every other job in the workflow.")
        else:
            needed = set([gate["needs"]] if isinstance(gate["needs"], str) else gate["needs"])
            missing = sorted(set(jobs) - needed - {GATE_JOB})
            if missing:
                fail(f"{GATE_JOB} must need every other job; it misses: {', '.join(missing)}.")
        mode_jobs = [
            job_id for job_id, job in jobs.items()
            if any(_text(step.get("uses")).startswith(CI_MODE_ACTION) for step in job.get("steps") or [])
        ]
        if not mode_jobs:
            fail(f"A job must run {CI_MODE_ACTION}v1 to pick the tier.")
        for job_id in mode_jobs:
            job_permissions = jobs[job_id].get("permissions", doc.get("permissions"))
            if not _grants_checks_read(job_permissions):
                fail(f"Job {job_id} runs ci-mode and needs `checks: read` to skip a push the queue already tested.")
    return findings


def _needs(job: dict[str, Any]) -> list[str]:
    needs = job.get("needs") or []
    return [needs] if isinstance(needs, str) else list(needs)


def _tier_skipped_jobs(jobs: dict[str, Any]) -> set[str]:
    """Jobs a fast-tier run skips: those whose `if` reads the tier, and those that need one."""
    skipped = {job_id for job_id, job in jobs.items() if "outputs.full" in _text(job.get("if"))}
    grew = True
    while grew:
        grew = False
        for job_id, job in jobs.items():
            if (job_id not in skipped and any(n in skipped for n in _needs(job))
                    and not any(f in _text(job.get("if")) for f in STATUS_FUNCTIONS)):
                skipped.add(job_id)
                grew = True
    return skipped


def _reports(job_id: str, job: dict[str, Any], context: str) -> bool:
    """Whether the job reports `context`: as its name, a matrix leg `name (…)`, or a reusable workflow's `name / …`."""
    name = _text(job.get("name")) or job_id
    if "${{" in name:
        return context.startswith(name.split("${{")[0])
    return context == name or context.startswith((f"{name} (", f"{name} / "))


def required_check_problems(contexts: list[str], merge_group_docs: list[dict[Any, Any]]) -> list[str]:
    """Explain each required context that would leave a pull request or merge group waiting."""
    problems = []
    for context in contexts:
        producers = []  # (job id, skipped by the fast tier, the name it reports when skipped)
        for doc in merge_group_docs:
            jobs: dict[str, Any] = doc.get("jobs") or {}
            skipped = _tier_skipped_jobs(jobs)
            producers += [
                (job_id, job_id in skipped, _text(job.get("name")) or job_id)
                for job_id, job in jobs.items()
                if _reports(job_id, job, context)
            ]
        if not producers:
            problems.append(f"Required check {context!r} comes from no workflow that triggers on merge_group, "
                            "so the merge queue would wait for it forever.")
        # A skipped job reports one check under its own name: a skipped matrix
        # job doesn't expand into its legs, and a skipped reusable-workflow
        # call reports none of the called workflow's jobs.
        elif all(skipped and context != name for _, skipped, name in producers):
            problems.append(f"Required check {context!r} comes from job {producers[0][0]}, which the fast tier "
                            f"skips; a skipped job reports only its own name. Require {GATE_JOB} instead.")
    return problems


def required_contexts(repo: str) -> list[str] | None:
    try:
        out = subprocess.run(
            ["gh", "api", f"repos/{repo}"], check=True, capture_output=True, text=True
        ).stdout
        branch = json.loads(out)["default_branch"]
        out = subprocess.run(
            ["gh", "api", f"repos/{repo}/rules/branches/{branch}"], check=True, capture_output=True, text=True
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"note: skipped the required-check rule: cannot read the rules of {repo} ({error})")
        return None
    contexts = []
    for rule in json.loads(out):
        if rule["type"] != "required_status_checks":
            continue
        for check in rule["parameters"]["required_status_checks"]:
            if check.get("integration_id") in (None, GITHUB_ACTIONS_APP_ID):
                contexts.append(check["context"])
    return contexts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", nargs="?", default=".", help="repository checkout (default: .)")
    parser.add_argument("--workflows", help="workflow directory (default: ROOT/.github/workflows)")
    parser.add_argument("--repo", help="OWNER/NAME: also check the default branch's required checks")
    args = parser.parse_args()

    root = pathlib.Path(args.root)
    directory = pathlib.Path(args.workflows) if args.workflows else root / ".github" / "workflows"
    findings: list[Finding] = []
    gate_files = []
    merge_group_docs = []
    for path in sorted([*directory.glob("*.yml"), *directory.glob("*.yaml")]):
        doc = yaml.safe_load(path.read_text()) or {}
        shown = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
        findings += check_workflow(shown, doc)
        if GATE_JOB in (doc.get("jobs") or {}):
            gate_files.append(shown)
        if "merge_group" in _triggers(doc):
            merge_group_docs.append(doc)

    if len(gate_files) != 1:
        findings.append(Finding(str(directory), f"Exactly one workflow must define {GATE_JOB}; found {len(gate_files)}."))
    if args.repo:
        contexts = required_contexts(args.repo)
        for problem in required_check_problems(contexts or [], merge_group_docs):
            findings.append(Finding(str(directory), problem))

    annotate = os.environ.get("GITHUB_ACTIONS") == "true"
    for finding in findings:
        print(f"::error file={finding.path}::{finding.message}" if annotate else f"{finding.path}: {finding.message}")
    if findings:
        print(f"{len(findings)} finding(s). The CI shape is described in "
              "https://github.com/cocoindex-io/.github/blob/main/CI.md")
        return 1
    print("CI conforms to the CocoIndex CI shape.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
