<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://cocoindex.io/blobs/github/homepage/enterprise-hero-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://cocoindex.io/blobs/github/homepage/enterprise-hero-light.svg">
    <img src="https://cocoindex.io/blobs/github/homepage/enterprise-hero-light.svg" alt="Enterprise corpus — codebase, Slack, meeting notes, and documentation — flowing continuously through the CocoIndex incremental sync engine into a production AI agent with always-fresh context. Only the Δ (delta) is reprocessed on every change." width="100%" draggable="false"/>
  </picture>
</p>
<h1 align="center">Your agents deserve <em>fresh context.</em></h1>

<p align="center">
  <strong>Star us&nbsp;❤️&nbsp;→</strong>&nbsp;<a href="https://github.com/cocoindex-io/cocoindex" title="Star CocoIndex on GitHub"><picture><source media="(prefers-color-scheme: dark)" srcset="https://cocoindex.io/blobs/github/homepage/star-btn-small-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://cocoindex.io/blobs/github/homepage/star-btn-small-light.svg"><img src="https://cocoindex.io/blobs/github/homepage/star-btn-small-light.svg" alt="Star CocoIndex on GitHub" height="36" align="absmiddle"/></picture></a> &nbsp;·&nbsp;
  <a href="https://cocoindex.io" title="cocoindex.io homepage"><picture><source media="(prefers-color-scheme: dark)" srcset="https://cocoindex.io/blobs/github/homepage/coco-inline-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://cocoindex.io/blobs/github/homepage/coco-inline-light.svg"><img src="https://cocoindex.io/blobs/github/homepage/coco-inline-light.svg" alt="cocoindex.io homepage" height="36" align="absmiddle"/></picture></a> &nbsp;·&nbsp;
  <a href="https://cocoindex.io/docs" title="CocoIndex documentation"><picture><source media="(prefers-color-scheme: dark)" srcset="https://cocoindex.io/blobs/github/homepage/docs-inline-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://cocoindex.io/blobs/github/homepage/docs-inline-light.svg"><img src="https://cocoindex.io/blobs/github/homepage/docs-inline-light.svg" alt="CocoIndex documentation" height="36" align="absmiddle"/></picture></a> &nbsp;·&nbsp;
  <a href="https://discord.com/invite/zpA9S2DR7s" title="Join the CocoIndex Discord"><picture><source media="(prefers-color-scheme: dark)" srcset="https://cocoindex.io/blobs/github/homepage/discord-inline-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://cocoindex.io/blobs/github/homepage/discord-inline-light.svg"><img src="https://cocoindex.io/blobs/github/homepage/discord-inline-light.svg" alt="Join the CocoIndex Discord" height="36" align="absmiddle"/></picture></a>
</p>

<p align="center">CocoIndex turns codebases, meeting notes, inboxes, Slack, PDFs, and videos into live, continuously fresh context for your AI agents and LLM apps to reason over effectively — with minimal incremental processing. Get your production AI agent ready in 10 minutes with reliable, continuously fresh data — no stale batches, no context gap.
</p>
<p align="center">
  <b>Incremental</b> · only the delta &nbsp;·&nbsp; <b>Any scale</b> · parallel by default &nbsp;·&nbsp; <b>Declarative</b> · Python, 5 min
</p>

<div align="center">

[![stars](https://img.shields.io/github/stars/cocoindex-io/cocoindex?style=flat-square&label=stars&color=FB6A76)](https://github.com/cocoindex-io/cocoindex)
[![downloads](https://img.shields.io/pepy/dt/cocoindex?style=flat-square&label=downloads&color=16A534)](https://pepy.tech/projects/cocoindex)
[![pypi](https://img.shields.io/pypi/v/cocoindex?style=flat-square&label=pypi&color=E59A63)](https://pypi.org/project/cocoindex/)
[![python](https://img.shields.io/badge/python-3.10--3.13-3572A5?style=flat-square)](https://www.python.org/)
[![rust](https://img.shields.io/badge/rust-core-db6d28?style=flat-square)](https://www.rust-lang.org/)
[![license](https://img.shields.io/badge/license-Apache--2.0-5B5BD6?style=flat-square)](https://opensource.org/licenses/Apache-2.0)
[![discord](https://img.shields.io/discord/1314801574169673738?style=flat-square&logo=discord&logoColor=white&label=discord&color=5865F2)](https://discord.com/invite/zpA9S2DR7s)

</div>

<br/>

<h3 align="center">Get started</h3>

```sh
pip install -U --pre cocoindex     # v1 is in preview — the --pre flag is required
```

Declare *what* should be in your target — CocoIndex keeps it in sync forever, recomputing only the Δ.

```python
import cocoindex as coco
from cocoindex.connectors import localfs, postgres
from cocoindex.ops.text import RecursiveSplitter

@coco.fn(memo=True)                          # ← cached by hash(input) + hash(code)
async def index_file(file, table):
    for chunk in RecursiveSplitter().split(await file.read_text()):
        table.declare_row(text=chunk.text, embedding=embed(chunk.text))

@coco.fn
async def main(src):
    table = await postgres.mount_table_target(PG, table_name="docs")
    table.declare_vector_index(column="embedding")
    await coco.mount_each(index_file, localfs.walk_dir(src).items(), table)

coco.App(coco.AppConfig(name="docs"), main, src="./docs").update_blocking()
```

<p align="center">Run once to backfill. Re-run anytime — only the changed files re-embed.</p>

<br/>

<h2 align="center">What can you <em>build?</em></h2>

<p align="center"><a href="https://github.com/cocoindex-io/cocoindex/tree/v1/examples"><b>See all 20+ examples · updated every week →</b></a></p>

| Codebase Indexing | Auto-Updating Knowledge Graph from Meeting Notes |
|-------------------|--------------------------------------------------|
| <img width="500" src="https://github.com/user-attachments/assets/d89f030a-1b03-4c87-b45c-ed253bff235c" alt="codebase indexing" /> | <img width="500" src="https://github.com/user-attachments/assets/e24563a0-c930-4c92-94b1-432c41155e64" alt="auto-updating knowledge graph" /> |
| [**Fork & Go: Realtime Codebase Indexing**](https://github.com/cocoindex-io/realtime-codebase-indexing) | [**Fork & Go: Meeting Notes Knowledge Graph**](https://github.com/cocoindex-io/meeting-notes-knowledge-graph) |

<br/>

<h2 align="center">Community</h2>

<p align="center">
  <a href="https://discord.com/invite/zpA9S2DR7s">Discord</a> &nbsp;·&nbsp;
  <a href="https://www.youtube.com/@cocoindex-io">YouTube</a> &nbsp;·&nbsp;
  <a href="https://cocoindex.io/blogs/">Blog</a> &nbsp;·&nbsp;
  <a href="https://x.com/cocoindex_io">X</a> &nbsp;·&nbsp;
  <a href="https://www.linkedin.com/company/cocoindex">LinkedIn</a>
</p>

<p align="center">
  📝 <a href="https://cocoindex.io/docs/about/contributing"><b>Contributing guide</b></a> &nbsp;·&nbsp;
  🐛 <a href="https://github.com/cocoindex-io/cocoindex/labels/good%20first%20issue"><b>good first issues</b></a> &nbsp;·&nbsp;
  💬 <a href="https://discord.com/invite/zpA9S2DR7s"><b>Say hi on Discord</b></a>
</p>

<br/>

<p align="center"><sub>Apache 2.0 · © CocoIndex contributors 🥥</sub></p>
