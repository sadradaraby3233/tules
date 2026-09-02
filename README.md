# TULES

A local, model-independent coding tool framework controlled through the clipboard.

TULES does not connect to an AI service. Any AI model that can produce the documented
JSON commands can inspect and modify a local project through TULES:

- the **AI model** decides what to inspect, change, and verify;
- **TULES** performs the filesystem, search, replacement, analysis, and shell work;
- the **user** copies commands to TULES and pastes results back into the conversation.

> **Using TULES with an AI model?** Run `tules --prompt --copy` and paste the result into
> the chat. That is under a thousand characters, and it is all the model needs: TULES
> serves the rest of its own documentation on demand. See
> [Working inside a small context window](#working-inside-a-small-context-window).
>
> The full manual, **[AI_TOOL_GUIDE.md](AI_TOOL_GUIDE.md)**, is still there as the human
> reference and for models with a large context to spare. This README is intentionally
> shorter and intended for repository users and contributors.

## Working inside a small context window

TULES is designed for the realistic case: a free chatbot account with a short context
window, and a human doing the copying. Nothing is automated against any chat service —
you copy a block out and paste a result back, which is why TULES never needs an API key
or a login. It also means every round trip costs you an action, so the design spends
bytes and round trips carefully.

Three things follow from that.

**1. You do not paste the manual.** Run:

```bash
tules --prompt --copy
```

That is a 992 character bootstrap: the `edit: ... endedit` envelope, how to read a
result, four rules, and one escape hatch. TULES serves the rest of its own documentation
on demand.

| Command | Returns | Size |
| --- | --- | --- |
| `{"action":"help"}` | every action, grouped, with its required arguments | ~860 characters |
| `{"action":"help","name":"replace"}` | that action's arguments, caveat, and a working example | ~300–550 characters |

**2. A wrong guess costs no round trip.** If a command is called with a missing or
malformed argument, the failure carries that action's usage, and an unknown action name
returns the index. The model corrects itself on its next turn instead of spending a
turn asking. Guessing is cheaper than looking up, so the prompt tells it to guess.

**3. Results are windowed, and say so.** Every value the model sees is capped. When a
value is cut, the reply says so in words rather than in a quiet footnote, and reads
return the exact command to continue:

```text
MESSAGE: Read lines 1-64 of tules/editor.py
DETAILS:
  total_lines: 547
  truncated: True
  next: {"action":"read_file","file":"tules/editor.py","start_line":65}  (483 of 547 lines still unread)
```

Command output is cut from the *front* instead, because a test or build run states its
verdict last. Use `--budget` to match your chatbot:

```bash
tules . --budget 800     # small free-tier window
tules . --budget 4000    # a model with room to spare
```

A complete six-turn session at `--budget 800` — bootstrap, discovery, a file read, a
wrong guess, the edit, and verification — costs about **1,300 tokens, roughly 16% of an
8k window**. Pasting `AI_TOOL_GUIDE.md` instead costs about 12,700 tokens, which does
not fit at all.

Because the usage table is checked against the live registry by the test suite, what
`help` returns cannot drift away from what the code does.

## Highlights

- Model-independent clipboard protocol — no API key, login, or model SDK.
- One universal `replace` action: exact, quote-normalized, whitespace, token, Python AST,
  context, and fuzzy matching, rejecting ambiguity rather than guessing.
- Workspace-confined access, timestamped backups, atomic writes, and per-file undo.
- Python and JSON parsed before a write lands; bracket balance enforced for brace
  languages; `.gitignore`-aware search.
- Literal, regex, fuzzy, glob, and filtered content search across many languages.
- Bash and PowerShell execution, web search and retrieval, notebook cell editing, static
  review, symbol extraction, dependency checks, and batch validation.

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
tules --prompt           # print the short bootstrap prompt for the AI chat
tules --prompt --copy    # ... and put it straight on the clipboard
tules . --budget 800     # shrink results to suit a small context window
tules . --actions        # print all registered actions
tules . --no-shell       # disable Bash, PowerShell, and run
tules . --exec cmd.json  # execute one JSON payload file and exit
```

The supplied directory is the workspace root. File tools cannot escape it.

## What using TULES is actually like

Be clear about the shape of this tool before you start, because it is not an
autonomous agent and does not pretend to be.

**You are the transport.** TULES never talks to a chat service. There is no API key, no
login, no browser automation — you copy a command block out of the chat and paste a
result back. That is what keeps TULES clear of any chat provider's terms, and it is also
the main cost: **one command block per copy-paste, and you do that by hand.** A small
change is three or four round trips. A careful multi-file change is fifteen or twenty.

**The model is the brain and it can be wrong.** TULES executes what it is told. The
guards below catch structural damage, not bad judgement. Every backup, every `STATUS:
FAILED`, and every review warning is there because a model will, eventually, try
something wrong.

**A realistic first session:**

1. `tules .` in the project, `tules --prompt --copy`, paste into the chat.
2. Give it the task. It replies with `{"action":"help"}` and `{"action":"analyze"}`.
3. Copy that block. TULES runs it and puts the result on your clipboard. Paste back.
4. It searches, reads the relevant region, proposes an edit. Paste, run, paste back.
5. It runs your tests through `bash`, reads the failures, fixes them.
6. You review `git diff` yourself before committing. Always.

Expect roughly 1,300 tokens of context for a short session at `--budget 800`. Expect to
spend more of your own attention on copying than on reading the code.

### Projects this suits

- **Python**, most of all. It is the only language with a real parser in the write path,
  AST-aware matching, and syntax refusal before a write lands.
- **Small and mid-sized codebases** — up to a few hundred files — where you can name the
  file or describe the symbol. Discovery costs round trips, so a project you already
  know is much cheaper than one you do not.
- **Projects with a fast, single-command test suite.** `pytest -q`, `npm test`, `go
  test ./...`. The verify step is what makes the loop trustworthy, and a slow suite makes
  it painful.
- **Text-shaped work**: config files, documentation, JSON fixtures, scripts, a
  well-contained refactor, adding tests, chasing a specific bug.
- **Learning or reviewing a codebase**, where `analyze`, `extract_symbols`, and
  `impact_check` do the reading and you do the thinking.

### Where to be careful

- **Languages other than Python and JSON have a weaker guard.** JavaScript, TypeScript,
  Go, Rust, Java, C#, C, C++, PHP, and Swift get a bracket-balance check, which refuses an
  edit that leaves delimiters unbalanced. That catches the common damage from a bad
  replacement. It is not a parser and will not catch a type error, a missing semicolon,
  or a wrong identifier. **Run the project's own build or tests after editing them.**
- **Everything else — YAML, TOML, HTML, CSS, SQL, Markdown, shell — has no write guard at
  all.** A broken edit is written to disk. The backup is your safety net.
- **Large files cost real turns.** Results are windowed, so a 3,000-line file takes many
  reads to work through. Narrow first with `grep` or `extract_symbols`, then read only
  the region you need.
- **Batches are not transactional.** Commands in an array run in order, and a failure
  part-way through leaves the earlier edits applied. Use `validate_batch` first for
  anything that must land together, and check each `[COMMAND n/N]` status.
- **`undo` is one step deep, per file.** It restores that file's most recent backup.
  Calling it twice does not walk back two edits. For real history, use git.
- **Shell actions run with your full user permissions**, in the workspace directory.
  `bash`, `powershell`, and `run` are ordinary subprocesses — they are not sandboxed. Use
  `--no-shell` if you do not want the model executing anything.
- **`web_search` scrapes a search engine's HTML.** It has no API key and no stability
  guarantee; it will break when the page markup changes. Treat it as a convenience.
- **Ignored files are skipped in search, not protected.** `.gitignore` now keeps build
  output and secret files out of `search`, `grep`, and `glob`, but a file named directly
  is still read. Do not rely on this as a security boundary.

### Where not to use it

- **Anything where an unreviewed write is dangerous**: production configuration, secrets,
  database migrations, infrastructure-as-code, deployment scripts. The airgap is a human
  pasting quickly, which is not the same as a human reading carefully.
- **Large monorepos.** Whole-project search reads every text file under the root each
  time. It will work and it will be slow, and discovery will dominate your round trips.
- **Refactors that must be atomic across many files** — a rename touching thirty call
  sites. Nothing rolls back, and you will be reconciling a half-applied change by hand.
- **Binary, generated, or vendored files.** Non-UTF-8 files are rejected outright, and
  files over 4 MB are skipped by search.
- **As an unattended agent.** There is no autonomous loop by design. If you want
  something that runs on its own, this is the wrong tool.
- **On a repository with uncommitted work you cannot afford to lose.** Commit or stash
  first. TULES backs up every file it touches under `.tules_backups/`, but git is the
  real safety net.

### The honest summary

TULES is a careful pair of hands for a model that cannot reach your filesystem. It is
good at making a specific change to a specific file and proving the change worked. It is
slow, manual, and deliberately un-autonomous. If those are acceptable, the guards and the
backups make it a safe way to let a free chatbot do real work on real code.

## Basic workflow

1. Start TULES in the project you want to modify.
2. Paste `tules --prompt` output into your AI chat, then give it your task.
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

`replace` is the canonical string and block replacement action. It takes the path as
`file` or `file_path`, the existing text as `old_string`/`old_str`/`search`, and the new
text as `new_string`/`new_str`/`replace_with`.

```text
edit:
{"action":"replace","file":"src/app.py","old_string":"def old_name():","new_string":"def new_name():"}
endedit
```

One universal engine tries, in order: unique exact match; quote-normalized match with
typography preserved; whitespace-insensitive multiline match with indentation adapted;
token-equivalent lines; Python AST function/class match; then a confidence-gated context
or fuzzy match. It never silently picks among duplicates — on an ambiguous match, add
`context_before`/`context_after`, pass `match_id`, or set `replace_all: true`.
`confidence_threshold` moves the fuzzy floor and `reason` labels the edit. An empty
search creates a missing file or fills an empty one, but cannot overwrite a non-empty
file.

Older names (`edit`, `str_replace`, `surgical_replace`, `context_replace`,
`search_and_replace_all`, `smart_replace`, `confirm_smart_replace`) still route here;
new integrations should use `replace`.

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
| `extract_symbols` | Extract functions, classes, and imports (Python AST; many languages via patterns) |
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
| `memory` | Read, append to, or list local notes (`scratchpad`, `todo`, or any custom target) |
| `list_actions` / `help` | Serve the live action index, or one action's usage via `name` |

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

`web_search` queries Google without an API key. `web_fetch` retrieves a page as text,
HTML, JSON, links, or filtered elements (`mode`, plus `tag`/`id`/`class`), and pages
long results with `start_line`/`end_line` or `start_char`/`end_char`. `download_url`
saves a file into the workspace, refusing to clobber an existing one unless
`overwrite: true`.

```text
edit:
{"action":"web_fetch","url":"https://docs.python.org/3/library/pathlib.html","mode":"text"}
endedit
```

All three allow only public HTTP(S) destinations: they reject credentials and
private, local, or reserved addresses, validate redirects, enforce timeouts, and cap
response sizes. Search parses Google's HTML and has no stability guarantee — when the
markup changes it returns fewer results or none, and `web_fetch` remains available.
Full parameter reference is in [AI_TOOL_GUIDE.md](AI_TOOL_GUIDE.md).

## Safety model

**Workspace confinement.** Paths resolve against the configured root. Escaping via `..`,
absolute outside paths, or symlinks is rejected.

**Backups.** Files are copied under `.tules_backups/` before mutation, with mirrored
directories and timestamped names; rapid edits in the same second get unique backups
rather than overwriting history. The newest ten per file are kept. Writes are atomic
same-directory replacements that preserve permissions, so an interrupted write cannot
leave a partial file. `undo` restores that file's latest backup — one step, not a stack.

**Write guards**, applied before a create, overwrite, replacement, insertion, deletion,
or line replacement, with the original left untouched on refusal:

| Files | Check | Catches |
| --- | --- | --- |
| `.py` | compiled with the real parser | any syntax error |
| `.json` | parsed | any malformed JSON |
| `.js` `.jsx` `.mjs` `.cjs` `.ts` `.tsx` `.java` `.cs` `.kt` `.scala` `.c` `.h` `.cpp` `.hpp` `.cc` `.go` `.rs` `.php` `.swift` | bracket balance | an edit that leaves `()`, `[]`, or `{}` unbalanced |
| everything else | none | nothing — the backup is your safety net |

The bracket check is not a parser. It judges the edit against the original file, so it
refuses only when a balanced file becomes unbalanced; a file it cannot lex (a raw string,
a regex literal) is left alone rather than blocked. It will not catch a type error or a
wrong identifier — build or test after editing these languages.

**Ignored files.** `search`, `grep`, and `glob` skip what the workspace's `.gitignore`
excludes, so build output and secret files do not reach the chat. A file named directly
is still read, so this reduces noise and accidental exposure — it is not a security
boundary. `--all-files` turns it off.

**Line endings.** Normalized internally; existing LF or CRLF is restored on save.

**Automatic review.** After a successful mutation, TULES reviews the target when its path
is in the payload and attaches findings as warnings.

## Project organization

```text
tules/
  agent.py          dispatch, post-edit review, and usage-on-misuse
  registry.py       command registration, aliases, and argument helpers
  guide.py          the bootstrap prompt and the per-action usage help serves
  commands/         one module per family: file_tools, edits, search, review,
                    shell, web — each registers its actions in the registry
  editor.py         replacement cascade, mutation guards, and file lifecycle
  structure.py      bracket-balance guard for the brace languages
  matching.py       normalization, indentation, and fuzzy block scoring
  workspace.py      path confinement, encoding, writes, and backups
  ignores.py        .gitignore parsing, so search skips excluded files
  analysis.py       symbols, reviews, duplicate and dependency analysis
  protocol.py       edit-block extraction and tolerant JSON decoding
  formatting.py     result rendering and the context budget
  monitor.py        clipboard loop
  cli.py            command-line interface
tests/              unit and integration tests
AI_TOOL_GUIDE.md    complete model-facing operating manual
```

Protocol, workspace access, matching, mutation, analysis, and command adapters are kept
separate so a contributor — or another AI model — can change one area without
reverse-engineering the whole project.

## Testing

```sh
pytest -q
ruff check tules tests
```

The suite covers every action end to end, replacement edge cases, path confinement, the
write guards, the context budget, `.gitignore` handling, and shell behavior. A few tests
depend on POSIX permissions or Bash and are expected to fail on Windows.

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
