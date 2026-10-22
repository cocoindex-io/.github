"""Tests for check_ci_conformance.py. Run: uv run --with pyyaml --with pytest pytest scripts"""

import pathlib

import yaml

from check_ci_conformance import check_workflow, required_check_problems

TEMPLATE = pathlib.Path(__file__).parent.parent / "workflow-templates" / "ci.yml"


def template() -> dict:
    return yaml.safe_load(TEMPLATE.read_text())


def messages(doc: dict) -> list[str]:
    return [f.message for f in check_workflow("ci.yml", doc)]


def test_template_conforms() -> None:
    assert messages(template()) == []


def test_gate_workflow_needs_merge_group() -> None:
    doc = template()
    del doc[True]["merge_group"]
    assert any("merge_group" in m for m in messages(doc))


def test_types_need_ready_for_review_and_stacked() -> None:
    doc = template()
    doc[True]["pull_request"]["types"] = ["opened", "synchronize"]
    found = messages(doc)
    assert any("ready_for_review" in m for m in found)
    assert any("stacked" in m for m in found)


def test_job_without_draft_guard() -> None:
    doc = template()
    doc["jobs"]["changes"]["if"] = "true"
    assert any("Job changes must skip drafts" in m for m in messages(doc))


def test_gate_must_run_always_and_need_every_job() -> None:
    doc = template()
    doc["jobs"]["ci-gate"]["if"] = "github.event.pull_request.draft != true"
    doc["jobs"]["ci-gate"]["needs"] = ["changes"]
    found = messages(doc)
    assert any("always()" in m for m in found)
    assert any("misses: test" in m for m in found)


def test_concurrency_required() -> None:
    doc = template()
    del doc["concurrency"]
    assert any("concurrency" in m for m in messages(doc))


def test_ci_mode_and_checks_permission() -> None:
    doc = template()
    doc["jobs"]["changes"]["permissions"] = {"contents": "read"}
    assert any("checks: read" in m for m in messages(doc))
    doc["jobs"]["changes"]["steps"] = [s for s in doc["jobs"]["changes"]["steps"] if "ci-mode" not in str(s.get("uses"))]
    assert any("to pick the tier" in m for m in messages(doc))


def test_plain_pull_request_workflow() -> None:
    doc = yaml.safe_load("""
on:
  pull_request:
    paths: [docs/**]
jobs:
  build:
    runs-on: ubuntu-latest
    steps: [{run: make}]
""")
    found = messages(doc)
    assert any("ready_for_review" in m for m in found)
    assert any("concurrency" in m for m in found)
    assert any("Job build must skip drafts" in m for m in found)
    assert not any("stacked" in m or "merge_group" in m for m in found)


def test_branch_filtered_workflow_needs_stacked() -> None:
    doc = yaml.safe_load("""
on:
  pull_request:
    branches: [main]
    types: [opened, synchronize, reopened, ready_for_review]
concurrency:
  group: x-${{ github.event.pull_request.number }}
  cancel-in-progress: true
jobs:
  fast-check:
    if: github.event.pull_request.draft != true
    runs-on: ubuntu-latest
""")
    assert [m for m in messages(doc) if "stacked" in m]


def test_required_contexts_match_job_names_and_matrix_prefixes() -> None:
    doc = yaml.safe_load("""
on: [merge_group]
jobs:
  ci-gate: {runs-on: x}
  pre-commit: {runs-on: x}
  rust:
    name: rust-checks (${{ matrix.os }})
    runs-on: x
""")
    contexts = ["ci-gate", "pre-commit (3.11)", "rust-checks (ubuntu-latest)", "fast-check"]
    problems = required_check_problems(contexts, [doc])
    assert len(problems) == 1 and "'fast-check'" in problems[0]


def test_required_check_from_tier_skipped_matrix_job() -> None:
    doc = yaml.safe_load("""
on: [merge_group]
jobs:
  pre-commit:
    needs: changes
    if: needs.changes.outputs.full == 'true'
    strategy: {matrix: {python-version: ['3.11']}}
    runs-on: x
""")
    problems = required_check_problems(["pre-commit (3.11)"], [doc])
    assert len(problems) == 1 and "Require ci-gate instead" in problems[0]


def test_status_function_overrides_inherited_draft_skip() -> None:
    doc = template()
    doc["jobs"]["test"]["if"] = "!cancelled()"
    assert any("Job test must skip drafts" in m for m in messages(doc))


def test_short_form_concurrency() -> None:
    doc = template()
    doc["concurrency"] = "ci-${{ github.event.pull_request.number }}"
    assert any("cancel-in-progress" in m for m in messages(doc))


def test_required_check_match_is_exact_or_expanded() -> None:
    doc = yaml.safe_load("""
on: [merge_group]
jobs:
  test: {runs-on: x}
""")
    problems = required_check_problems(["test-e2e"], [doc])
    assert len(problems) == 1 and "no workflow that triggers on merge_group" in problems[0]


def test_required_check_from_tier_skipped_reusable_workflow() -> None:
    doc = yaml.safe_load("""
on: [merge_group]
jobs:
  changes: {runs-on: x}
  build-test:
    name: Build & Test
    needs: changes
    if: needs.changes.outputs.full == 'true' && needs.changes.outputs.build-test != 'false'
    uses: ./.github/workflows/_test.yml
""")
    problems = required_check_problems(["Build & Test / build-test (ubuntu-latest)", "changes"], [doc])
    assert len(problems) == 1 and "Build & Test / build-test" in problems[0]


def test_required_check_from_job_skipped_through_needs() -> None:
    doc = yaml.safe_load("""
on: [merge_group]
jobs:
  changes: {runs-on: x}
  build:
    needs: changes
    if: needs.changes.outputs.full == 'true'
    runs-on: x
  test:
    needs: build
    strategy: {matrix: {os: [a]}}
    runs-on: x
  report:
    needs: test
    if: always()
    runs-on: x
""")
    problems = required_check_problems(["test (a)", "report", "build"], [doc])
    assert len(problems) == 1 and "'test (a)'" in problems[0]
