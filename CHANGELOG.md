# Changelog

All notable changes to Chronicle MCP (`chronicle-mcp-server`) are documented here.
Entries before 1.6.1 are summarized from the existing GitHub releases and git tags.

## [Unreleased]

### Added
- `mcpb/`: an MCP Bundle (`.mcpb`) manifest, icon and launcher for Smithery's local (stdio) listing and other
  MCPB clients. The bundle runs the pinned PyPI release with `uvx`. A new CI job checks the manifest against
  the package version and the server's tools, validates it with the MCPB CLI and uploads the packed bundle.

### Removed
- `smithery.yaml`. Smithery no longer publishes stdio servers from a `startCommand`/`commandFunction` config;
  local servers are published as MCPB bundles.

## [1.6.2] - 2026-10-20

Tool-quality release driven by a full audit against Glama's TDQS rubric, Smithery's quality score and the MCP
spec. Tool names, parameters and defaults are unchanged.

### Fixed
- **The server failed to start on fresh installs.** `mcp>=1.0.0` resolved to mcp 2.x, which removed
  `mcp.server.fastmcp`. The dependency is now `mcp>=1.22,<2`.
- Tool execution errors (for example a missing chat file, an invalid date, or a failed import) now come back
  as MCP results with `isError: true` instead of looking like successful output. The Python
  `ChatConnector` API is unchanged.
- Unknown operation names no longer silently run a different operation. For example,
  `maintain_storage(op_type="bogus")` used to return capabilities and an unknown `insight_type` used to write
  a project brief. They are now rejected with a validation error, and the same applies to zero or negative
  counts.
- Two handoff receipts saved within the same second no longer overwrite each other. A numeric suffix is
  added on collision. The save result now also reports the `receipt_id` to use in `supersedes`.
- Topic tagging matches whole words, so "build" no longer tags a chat as `ui_design`.
- An explicitly set `CHRONICLE_BASE_DIR` now takes precedence over the folder saved in
  `~/.chronicle_settings.json`.
- `serverInfo` now reports name "Chronicle MCP" and Chronicle's own version; it used to report the mcp SDK
  version.
- `search_history` was registered twice.
- A leading `~` in `CHRONICLE_BASE_DIR` or `TRANSCRIPTS_DIR` is now expanded to your home folder.

### Added
- Rewritten descriptions for all 8 tools: what each does, when to use it instead of its siblings, side
  effects, and what it returns.
- Descriptions on every parameter (56), enum constraints on every operation selector, lower bounds on
  counts, and the expected keys of the handoff-receipt objects.
- Tool titles and annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`).
- Server `instructions`, a `recall_past_work(topic)` prompt, a title for `start_session`, and two resources:
  `chronicle://capabilities` and `chronicle://chats`.
- An output schema for `get_handoff_status`.
- `chronicle-mcp-server` console script and `chronicle serve`, which always start the stdio server (so
  `uvx chronicle-mcp-server` works), plus `chronicle --version`.
- `Dockerfile` and `.dockerignore` for Glama and other container-based inspectors, and a `smithery.yaml` for
  local stdio installs.
- `test_mcp_introspection.py`: starts the server over stdio and fails if any tool, parameter, prompt or
  resource loses its description, title or annotations, if errors stop setting `isError`, or if versions
  drift. CI also builds the Docker image and runs `initialize` and `tools/list` against it.
- `CHRONICLE_LOG_LEVEL` (default `WARNING`), which replaces the per-request INFO lines on stderr.

### Changed
- `smoke_test_live.py` is now a read-only live check over MCP that exits non-zero on failure. It used to
  call core methods without assertions and write exports and index files.
- `server.json`: added title, website URL, icon, `runtimeHint: uvx` and the optional environment variables,
  and removed fields the registry schema does not define.
- README: the tool reference documents annotations and enums, the Docker and `serve` usage, and the fact
  that workspace rule files are opt-in (`CHRONICLE_AUTO_CONFIGURE_RULES=1`).

## [1.6.1] - 2026-10-19

Discoverability, CI, and repository cleanup ([#3](https://github.com/Leviathan0x0/Chronicle-MCP/pull/3)). No changes to search or storage behavior.

### Added
- GitHub Actions CI (`.github/workflows/ci.yml`) on push and pull request: the unit tests and `test_all_tools.py` on Python 3.10, 3.11, 3.12 and 3.13, plus a job that runs `python -m build` and `twine check --strict`.
- PyPI metadata: project URLs (Homepage, Repository, Issues, Documentation, Changelog), keywords, and fuller classifiers (development status, audience, environment, topics, and Python 3.10 to 3.13).
- This changelog.

### Changed
- `maintain_storage(op_type="capabilities")` now lists all 8 tools (including `save_handoff_receipt` and `get_handoff_status`) and the `start_session` prompt, and reports `total_tools: 8` instead of 6.
- `test_all_tools.py` skips itself under `python -m unittest discover` (it is a standalone script) and still runs normally with `python test_all_tools.py`.
- License metadata uses the SPDX expression `license = "MIT"` (build now requires `setuptools>=77`), which clears the build deprecation warnings.
- README: a distinct title and tagline, a CI badge, correct tool counts (8 tools plus the `start_session` prompt instead of "6" or "27"), docs for `get_handoff_status` and `start_session`, corrected `save_handoff_receipt` parameters and test commands, and absolute image URLs so images render on PyPI.

### Removed
- Committed build artifacts (`dist/` and `chronicle_mcp_server.egg-info/`) and the generated `.chronicle_index.json` search index are no longer tracked. `.gitignore` now covers standard Python packaging and cache output.

## [1.6.0] - 2026-10-17

Release [v1.6.0](https://github.com/Leviathan0x0/Chronicle-MCP/releases/tag/v1.6.0).

- **Security hardening:** `realpath`/`commonpath` containment against allowed roots for imports, transcript sync, exports and briefs; symlink traversal guards; chunked gzip decompression with a 50 MB ceiling; validation of shebang-resolved executables in the CLI; removal of a ReDoS-prone regex in code-block summarization.
- **Search:** Okapi BM25 statistics scoped per client namespace with Robertson-Spärck Jones IDF; a fix for temporal-decay underflow on files without valid timestamps; a Unicode-aware tokenizer.
- **Handoff ledger:** fixed DAG traversal and closure resolution in `get_workspace_handoff_state`; normalized receipt timestamps; deleted duplicates are evicted from the search index during deduplication.
- **CLI and platform:** Windows `msvcrt` keyboard fallback; atomic file writes with thread locking; `.bak` recovery for corrupt index or config files; no stray config files from `update_json_config`; filename sanitization and collision counters in `split_export_file`; OpenCode MCP config support and a JSON-C comment parsing fix.

## 1.5.4 - 2026-06-29

Published to PyPI without a git tag or release (date is the version-bump commit). From the commit history:

- Fixed custom app validation and config save paths in the setup wizard, and added a CLI startup logo.

## [1.5.3] - 2026-06-16

Git tag `v1.0.3` (no GitHub release).

- Active-override resolver for handoff receipts, with a stale-closure test harness (`test_stale_closure.py`).

## [1.5.2] - 2026-06-16

Git tag and release [v1.0.2](https://github.com/Leviathan0x0/Chronicle-MCP/releases/tag/v1.0.2).

- Strict state-machine DAG schema for handoff receipts, head resolution over the active receipt chain, active invalidation (`stale_if`), and a coherence test.

## [1.5.1] - 2026-06-16

Git tag and release [v1.0.1](https://github.com/Leviathan0x0/Chronicle-MCP/releases/tag/v1.0.1).

- Agent ledgering and receipt aging: expanded handoff schema, append-only timestamped receipts, a workspace deduplication gate, and a steep (1-day half-life) recency decay for handoff search results.

## [1.5.0] - 2026-06-16

Git tag and release [v1.0.0](https://github.com/Leviathan0x0/Chronicle-MCP/releases/tag/v1.0.0), the first stable release.

- Six consolidated tools (`get_chat_logs`, `search_history`, `manage_session_state`, `sync_workspace_data`, `compile_project_insights`, `maintain_storage`) plus `save_handoff_receipt`; Okapi BM25 scoring; hybrid temporal and lexical session splitting; the `chronicle setup` terminal wizard.

## Earlier versions

Versions 1.0.x to 1.1.x were published to [PyPI](https://pypi.org/project/chronicle-mcp-server/#history) without changelog entries or git tags.

Note: the git tags `v1.0.0` to `v1.0.3` correspond to package versions 1.5.0 to 1.5.3. From `v1.6.0` on, tag names match package versions.

[1.6.2]: https://github.com/Leviathan0x0/Chronicle-MCP/compare/v1.6.1...HEAD
[1.6.1]: https://github.com/Leviathan0x0/Chronicle-MCP/compare/v1.6.0...v1.6.1
[1.6.0]: https://github.com/Leviathan0x0/Chronicle-MCP/releases/tag/v1.6.0
[1.5.3]: https://github.com/Leviathan0x0/Chronicle-MCP/compare/v1.0.2...v1.0.3
[1.5.2]: https://github.com/Leviathan0x0/Chronicle-MCP/compare/v1.0.1...v1.0.2
[1.5.1]: https://github.com/Leviathan0x0/Chronicle-MCP/compare/v1.0.0...v1.0.1
[1.5.0]: https://github.com/Leviathan0x0/Chronicle-MCP/releases/tag/v1.0.0
