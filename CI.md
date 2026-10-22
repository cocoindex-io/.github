# CI at CocoIndex

Each commit that lands gets one full CI run. Pull requests run a fast tier.
The merge queue runs the full tier on the exact commit that lands, and the
push to the default branch does not repeat it. This replaces a pattern where
every merge made every other open pull request rebase and re-run, which cost
CI runs in proportion to the square of the open pull requests.

The pieces in this repository:

| Path | What it is |
| --- | --- |
| [`workflow-templates/ci.yml`](workflow-templates/ci.yml) | The starter CI workflow. New repositories begin here. |
| [`actions/ci-mode`](actions/ci-mode/action.yml) | Decides the tier of a run (below). |
| [`scripts/check_ci_conformance.py`](scripts/check_ci_conformance.py) | Checks a repository's workflows against this page. |
| [`.github/workflows/ci-conformance.yml`](.github/workflows/ci-conformance.yml) | Runs that check; the organization ruleset requires it. |
| [`rulesets/`](rulesets/) and [`scripts/apply_rulesets.py`](scripts/apply_rulesets.py) | The organization ruleset and custom property, and the script that applies or checks them. |

## Tiers

| Run | Tier |
| --- | --- |
| A draft pull request | None. Every job skips. Mark the pull request ready when local checks pass. |
| A ready pull request whose base branch has a merge queue | Fast. The queue runs the full tier. |
| A ready pull request without a queue, a stack layer below the top | Fast. The top layer's run covers the whole stack. |
| A ready pull request without a queue, standalone or the top layer | Full. |
| A merge group | Full, on the commit that lands. |
| A push to the default branch | Full, unless the commit already passed `ci-gate`, as every merge-queue commit has. |
| The nightly schedule | Full. It keeps the default branch's caches current and catches flaky tests. |
| A manual run | Full. For early feedback on a branch: `gh workflow run CI.yml --ref <branch>`. |

The fast tier is what runs without the full tier: lint and format checks
such as a `fast-check` job, plus the always-running `changes` and `ci-gate`
jobs. A failed lookup in `ci-mode` falls back to the full tier, so an API
error costs runner time but never skips tests.

## The shape

The main CI workflow of each repository has these parts. The starter
workflow has all of them.

1. **Triggers.** `pull_request` with types `opened, synchronize, reopened,
   ready_for_review, stacked`, plus `merge_group`, `push`, `schedule` and
   `workflow_dispatch`.
2. **Concurrency.** A workflow-level group keyed on the pull request number,
   with `cancel-in-progress`, so a new push cancels the superseded run. Other
   events get a group of their own.
3. **Drafts skip.** Every job has `github.event.pull_request.draft != true`
   in its `if`, or needs a job that has it.
4. **A `changes` job** runs `cocoindex-io/.github/actions/ci-mode@v1` (it
   needs `checks: read`) and the path filter. Expensive jobs run when
   `full == 'true'` and the filter output is not `'false'`. The filter is
   skipped for a stack layer, and so is any other diff against the pull
   request's base branch: a stack layer's base is the layer below it, but
   the top layer's run stands in for the whole stack. Diff a stack layer
   against `github.event.pull_request.stack.base.ref`.
5. **A `ci-gate` job** with `if: always()` that needs every other job. It is
   the one check to require. A skipped job reports success, so a required
   check that can be skipped by a failure would let the failure merge.

Every other workflow that runs on pull requests has parts 2 and 3, the
`ready_for_review` type, and the `stacked` type when it filters on branches.
Every workflow that reports a required check triggers on `merge_group`, or
the queue waits for that check until it times out. Require `ci-gate`, plus
checks from jobs that run in every tier, such as `fast-check`. A matrix job
that the tier skips reports one check under its unexpanded name, so a
required `name (value)` check from it never arrives.

## The merge queue

The `ci-merge-queue` ruleset configures it: squash merges, every entry must
pass (`ALLGREEN`), and at most 4 builds at once. That build limit is the CI
quota: a queued pull request waits for a free build slot.

**How it builds.** Each queued pull request gets its own build of the base
branch plus every pull request ahead of it. Builds run in parallel up to the
limit. GitHub never tests several pull requests in one build. Head-only
grouping (`HEADGREEN`) changes which builds must pass, not how many run.

**When a build fails.** The queue removes the first failing pull request, and
the stack layers above it. It rebuilds the entries behind it without it, and
the passing entries ahead of it land. The first failing entry is the culprit,
so no separate bisection is needed. The pull request's owner fixes it and
queues it again. A failure that looks unrelated to the change gets one
re-queue before anyone investigates it, and a flaky test found that way gets
root-caused, not retried away.

## Stacked pull requests

Use a stack only when a pull request builds on another one. Independent pull
requests go to the queue on their own, which tests them together anyway.

- GitHub checks every layer against the stack's base, so a workflow filtered
  to `main` runs on every layer. A layer's `opened` event can arrive before
  its stack exists and miss that filter, which is why workflows also trigger
  on `stacked`.
- Land a stack from the top with `gh stack merge <top>`. Each layer becomes a
  queue entry, so the queue tests every prefix of the stack, and a failing
  layer leaves with the layers above it while the layers below land.
- Without a queue, only the top layer runs the full tier. Merge the whole
  stack from the top; a lower layer merged alone lands code that its own run
  did not test.

## Merge commits

The queue squashes. A pull request that must land as a merge commit, such as
an upstream merge, bypasses the queue: repository admins may merge pull
requests directly. Run the full tier on its branch first with
`gh workflow run`, wait for it to pass, then merge with
`gh pr merge --merge --admin`. Nothing else bypasses the queue.

## Caches

A merge-group run saves its caches under the queue's temporary branch, where
no later run can read them. The default branch's caches come from its push
runs and the nightly run, and every run can read those.

## Enforcement

A repository opts in by setting its `ci-tier` custom property to
`merge-queue`. The `ci-merge-queue` organization ruleset then applies to its
default branch: the merge queue, the `ci-gate` check, and the `ci-conformance`
workflow from this repository. Other required checks stay in the
repository's own rulesets.

- Apply or check the ruleset and property: `scripts/apply_rulesets.py
  [--check]`. It needs an organization owner with the `admin:org` scope, and
  the Change Management Policy asks that the change be announced.
- Check a repository locally:
  `uv run --with pyyaml scripts/check_ci_conformance.py PATH --repo OWNER/NAME`.
- A ruleset runs a required workflow only on `opened`, `synchronize` and
  `reopened` pull request events and on merge groups, and ignores the
  workflow's `types` and filters. `ci-conformance` therefore runs on drafts
  too.

## Changing this kit

Callers use the `v1` tag, and the ruleset runs `ci-conformance.yml` from it.
After merging a compatible change, move the tag:

```bash
git tag -f v1 origin/main && git push -f origin v1
```

A change that existing callers would fail goes to `v2`.

## Verified behavior

Checked on 2026-10-22 in a temporary private repository:

- A stack layer's pull request triggers a workflow filtered to `main`. Its
  payload has `stack.position`, `stack.size` and `stack.base.ref`.
- A layer created by `gh stack submit` missed its `opened` run. The `stacked`
  type fixed it, and concurrency cancelled the duplicate runs.
- A draft ran no jobs. Marking it ready started CI.
- `GITHUB_TOKEN` reads the branch rules, so `ci-mode` sees the merge queue.
- A three-layer stack produced three parallel merge-group builds, one per
  prefix, and one push run on `main`. With the middle layer broken, the
  bottom layer landed and the other two left the queue.
- The commit the queue pushes to `main` is the commit its merge group tested.
- A repository admin merged a pull request around the queue as a merge
  commit with both parents.
