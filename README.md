# TULES

A local, model-independent coding tool framework controlled through the clipboard.

TULES does not connect to an AI service. Any AI model that can produce the documented
JSON commands can inspect and modify a local project through TULES:

- the **AI model** decides what to inspect, change, and verify;
- **TULES** performs the filesystem, search, replacement, analysis, and shell work;
- the **user** copies commands to TULES and pastes results back into the conversation.

> **Using TULES with an AI model?** Give the model
> **[AI_TOOL_GUIDE.md](AI_TOOL_GUIDE.md)**. It contains the complete operating contract,
> command schemas, response formats, decision rules, recovery guidance, and examples.
> This README is intentionally shorter and intended for repository users and contributors.

## Highlights

- Model-independent clipboard protocol—no API key or model SDK required.
- One universal `replace` action instead of several competing replacement engines.
- Exact, normalized-quote, whitespace, token, Python AST, context, and fuzzy matching.
- Ambiguous replacements are rejected unless context, a candidate ID, or explicit
  replace-all behavior resolves them.
- Workspace-confined file access.
- Timestamped backups and per-file undo.
- Python syntax protection before writes are committed.
- CRLF/LF preservation.
- Literal, regular-expression, fuzzy, glob, and filtered content search.
- Google web search plus safe page retrieval, HTML/text/link/element extraction, and downloads.
- Structured Jupyter notebook cell editing.
- Bash and PowerShell execution with timeouts and structured results.
- Static review, symbol extraction, dependency checks, and batch validation.

## Requirements

- Python 3.9 or newer
- `pyperclip` (installed automatically)
- A working system clipboard
- Bash for the `bash` and backward-compatible `run` actions
- PowerShell 7 (`pwsh`) or Windows PowerShell for the optional `powershell` action

## Installation

From a clone of this repository:

```sh
pip install -e .
```

For development:

```sh
pip install -e ".[dev]"
pytest
```

## Running TULES

```sh
tules .
tules /path/to/project
python -m tules .
```

Useful options:

```sh
tules . --actions        # print all registered actions
tules . --no-shell       # disable Bash, PowerShell, and run
tules . --exec cmd.json  # execute one JSON payload file and exit
```

The supplied directory is the workspace root. File tools cannot escape it.

## Basic workflow

1. Start TULES in the project you want to modify.
2. Give your AI model [AI_TOOL_GUIDE.md](AI_TOOL_GUIDE.md) and your task.
3. Copy the model's response containing an `edit:` block.
4. TULES executes the JSON and writes a structured result to the clipboard.
5. Paste that result back into the model.
6. Continue until the model has inspected, changed, and verified the project.

## Command protocol

TULES ignores clipboard text unless it contains an `edit:` / `endedit` block:

```text
edit:
{"action":"read","file_path":"src/app.py","offset":1,"limit":200}
endedit
```

A JSON array runs a sequential batch:

```text
edit:
[
  {"action":"glob","pattern":"**/*.py"},
  {"action":"grep","pattern":"TODO","type":"py","output_mode":"content"}
]
endedit
```

TULES tolerates Markdown fences, trailing commas, and some common JSON formatting
mistakes, but valid JSON is recommended.

## Result format

A successful command returns plain text similar to:

```text
STATUS: SUCCESS
MESSAGE: Edited src/app.py
DETAILS:
  backup: .tules_backups/src/app_20260825_114604.py
  match_level: exact
  occurrences: 1
```

Failures return `STATUS: FAILED` and structured diagnostic details. A failed guarded
edit does not modify the target. Batch responses contain an individual status for every
command; batches are sequential and are not transactional.

## Universal replacement

`replace` is the canonical string and block replacement action:

```text
edit:
{
  "action":"replace",
  "file":"src/app.py",
  "old_string":"def old_name():\n    return 1",
  "new_string":"def new_name():\n    return 2"
}
endedit
```

Accepted field variants:

| Purpose | Fields |
| --- | --- |
| Path | `file` or `file_path` |
| Existing text | `old_string`, `old_str`, or `search` |
| Replacement text | `new_string`, `new_str`, or `replace_with` |
| Disambiguation | `context_before`, `context_after`, or `match_id` |
| Replace every occurrence | `replace_all: true` |
| Fuzzy matching floor | `confidence_threshold` |
| Audit label | `reason` |

The replacement cascade is:

1. unique exact match;
2. straight/curly quote-normalized match with typography preservation;
3. whitespace-insensitive multiline match with indentation adaptation;
4. token-equivalent line match;
5. Python function/class AST match;
6. confidence-gated context or fuzzy match.

It will not silently choose among unresolved duplicates. An empty search creates a
missing file or fills an empty file, but cannot overwrite a non-empty file.

Older action names remain accepted for existing integrations, but all route to the same
engine: `edit`, `str_replace`, `surgical_replace`, `context_replace`,
`search_and_replace_all`, `smart_replace`, and `confirm_smart_replace`. New integrations
should use `replace`.

## Available actions

Action names are case-insensitive.

### Read and discover

| Action | Purpose |
| --- | --- |
| `read` | Read a numbered line window using `offset` and `limit` |
| `read_file` | Read raw file text, optionally by line range |
| `view` | Read numbered lines suitable for quoting and line edits |
| `glob` | Find files using path wildcard patterns |
| `list_files` | Find files by a filename fragment |

### Search and inspect

| Action | Purpose |
| --- | --- |
| `grep` | Regex search with path/type/glob filters, context, modes, and pagination |
| `search` | Literal workspace search |
| `search_regex` | Lightweight regular-expression search |
| `search_fuzzy` | Find approximately matching lines |
| `analyze` | Summarize a file or survey the project |
| `extract_symbols` | Extract functions, classes, and imports |
| `review` | Run built-in static checks |
| `impact_check` | Find files that import or reference a module |
| `check_duplicates` | Find duplicate symbol definitions |
| `web_search` | Search the public web with Google |
| `web_fetch` | Retrieve page text, HTML, JSON, links, metadata, or selected elements |

### Modify files

| Action | Purpose |
| --- | --- |
| `replace` | Universal safe string/block replacement |
| `replace_by_line` | Replace an inclusive numbered line range |
| `insert` | Insert content after a line number |
| `delete` | Delete an inclusive line range |
| `diff_preview` | Preview an exact replacement without writing |
| `write` | Create or fully overwrite a file |
| `create_file` | Create a file and refuse an existing path |
| `delete_file` | Back up and delete a file |
| `undo` | Restore the newest backup for one file |
| `notebook_edit` | Insert, replace, or delete a notebook cell |
| `download_url` | Safely download a public URL into the workspace |

### Execute and coordinate

| Action | Purpose |
| --- | --- |
| `bash` | Run Bash in the workspace with a timeout |
| `powershell` | Run PowerShell when installed |
| `run` | Backward-compatible alias for Bash |
| `validate_batch` | Preflight supported commands without applying them |
| `memory` | Read or append local scratchpad/todo notes |
| `list_actions` / `help` | List the live action registry |

For exact schemas, return fields, failure modes, and examples for every action, see
[AI_TOOL_GUIDE.md](AI_TOOL_GUIDE.md).

## Shell execution

Bash example:

```text
edit:
{"action":"bash","command":"pytest -q","timeout":180,"description":"Run tests"}
endedit
```

PowerShell example:

```text
edit:
{"action":"powershell","command":"Get-ChildItem -Recurse","timeout":60}
endedit
```

Both return `stdout`, `stderr`, `exit_code`, shell metadata, and truncation status. Each
output stream retains its last 30,000 characters. Timeouts must be between 1–600 seconds. Background execution is intentionally not
supported in clipboard mode. If PowerShell is not installed, its action returns a clear
failure rather than interpreting the command in another shell.

Use `--no-shell` when command execution should be unavailable.

## Web tools

Search Google without an API key:

```text
edit:
{"action":"web_search","query":"Python pathlib documentation","limit":5}
endedit
```

Retrieve a readable page, its original HTML, parsed JSON, links, or structured elements:

```text
edit:
{"action":"web_fetch","url":"https://docs.python.org/3/library/pathlib.html","mode":"text"}
endedit
```

Text can be paged with `start_line`/`end_line`, and HTML with `start_char`/`end_char`.
`mode: "elements"` accepts optional `tag`, `id`, and `class` filters plus `offset` and
`limit`. `mode: "links"` resolves relative links against the final page URL. Responses
include the final URL after redirects, HTTP status, content type, byte count, title, and
page metadata. `mode: "html"` returns source HTML, while `mode: "json"` decodes JSON.

Download a linked file using `download_url`; provide `file` when the URL does not contain
a useful filename. Existing files are refused unless `overwrite: true`, in which case the
old file is backed up first. Network tools allow only public HTTP(S) destinations, reject
credentials and private/local/reserved addresses, validate redirects, enforce timeouts,
and cap response sizes. Google markup and anti-automation behavior can change, so search
may occasionally return fewer results; direct `web_fetch` remains available.

## Safety model

### Workspace confinement

Paths are resolved against the configured workspace. Escaping through `..`, absolute
outside paths, or resolving symlinks is rejected.

### Backups

Existing files are copied under `.tules_backups/` before mutation. Directory structure
is mirrored and filenames include timestamps. Rapid edits in the same second receive
unique backups instead of overwriting history. Writes use an atomic same-directory
replacement and preserve existing file permissions, so an interrupted write cannot leave
a partially written target. `undo` restores the latest backup for the requested file.

### Python syntax guard

Before committing a `.py` create, overwrite, replacement, insertion, deletion, or line
replacement, TULES compiles the resulting source. Invalid Python is rejected and the
original remains unchanged.

### Line endings

Text is normalized internally, while existing LF or CRLF style is restored on save.

### Automatic review

After successful mutations, TULES reviews the target when its path is present in the
payload and attaches a limited set of findings as warnings.

## Project organization

```text
tules/
  agent.py          dispatch and automatic post-edit review
  registry.py       command registration, aliases, and argument helpers
  commands/
    file_tools.py   reads, writes, search, notebooks, backups, and memory
    edits.py        universal replace, line edits, and diff preview
    search.py       native literal/regex/fuzzy and dependency searches
    review.py       analysis, review, and batch validation
    shell.py        Bash and PowerShell execution
  editor.py         replacement cascade, mutation guards, and file lifecycle
  matching.py       normalization, indentation, and fuzzy block scoring
  workspace.py      path confinement, encoding, writes, and backups
  analysis.py       symbols, reviews, duplicate and dependency analysis
  protocol.py       edit-block extraction and tolerant JSON decoding
  formatting.py     plain-text result rendering
  monitor.py        clipboard loop
  cli.py            command-line interface
tests/              unit and integration tests
AI_TOOL_GUIDE.md    complete model-facing operating manual
```

The modules intentionally separate protocol, workspace access, matching, mutation,
analysis, and command adapters so future contributors—or another AI model—can modify one
area without reverse-engineering the whole project.

## Testing

```sh
pytest -q
```

The suite includes unit tests, full action integration coverage, universal replacement
edge cases, path confinement, syntax guards, Bash behavior, and PowerShell availability
and command construction.

For linting:

```sh
ruff check tules tests
```

## Contributing

When adding or changing an action:

1. Register it in the appropriate `tules/commands/` module.
2. Keep filesystem mutation inside `Editor` and `Workspace` safeguards.
3. Add success and edge-case tests.
4. Update this user README when installation or public capabilities change.
5. Update `AI_TOOL_GUIDE.md` when schemas, decision rules, result fields, or failure
   behavior change.
6. Run the complete test and lint suites.

## License

See the repository license file for licensing terms.
