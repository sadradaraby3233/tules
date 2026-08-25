# TULES

A local code agent driven by the clipboard. You paste a command block into any chat
model's answer, copy it, and TULES applies it to your project and copies a plain text
reply back for you to paste into the chat.

TULES never talks to a model itself: it is the hands, the model is the brain.

## Install

```sh
pip install -e .
```

Python 3.9 or newer. The only runtime dependency is `pyperclip`.

## Run

```sh
tules .                  # watch the clipboard, edit the current directory
tules /path/to/project   # watch the clipboard, edit another project
python -m tules .        # same thing without installing the console script

tules . --actions        # list every supported action
tules . --no-shell       # refuse the run action
tules . --exec cmd.json  # apply one payload and exit (no clipboard involved)
```

## The protocol

Anything the model copies is ignored unless it contains a block like this:

```
edit:
{"action": "str_replace", "file": "app.py", "old_str": "x = 1", "new_str": "x = 2"}
endedit
```

The payload is one JSON object, or an array of them to run a batch. Markdown fences,
trailing commas and raw newlines inside strings are repaired before parsing.

The reply that lands on your clipboard looks like this:

```
STATUS: SUCCESS
MESSAGE: Edited app.py
DETAILS:
  backup: .tules_backups/app_20260825_114604.py
  reason: AI edit
```

### Actions

| Action | Writes | What it does |
| --- | --- | --- |
| `read_file` | | Read a file, optionally `start_line`/`end_line` |
| `view` | | Read a file with line numbers, ready to quote back |
| `list_files` | | List files matching a name fragment |
| `search` | | Find a literal string (`case_sensitive`, `whole_word`) |
| `search_regex` | | Find a regular expression |
| `search_fuzzy` | | Find similar lines (`threshold`) |
| `analyze` | | Summarize one file, or the project when `file` is omitted |
| `extract_symbols` | | List functions, classes and imports |
| `review` | | Static checks: syntax, unused imports, redefinitions, layout |
| `check_duplicates` | | Symbols defined more than once |
| `impact_check` | | Files importing or referencing a module |
| `diff_preview` | | Show the diff an edit would produce |
| `validate_batch` | | Dry-run a list of commands before sending them |
| `memory` | | Append to or read `.tules/scratchpad.md` |
| `run` | | Run a shell command in the workspace root |
| `list_actions` (`help`) | | List every action |
| `str_replace` | yes | Replace a string that occurs exactly once |
| `replace` | yes | Replace the first occurrence |
| `search_and_replace_all` | yes | Replace every occurrence |
| `surgical_replace` | yes | Exact, then whitespace agnostic, then token, then AST |
| `context_replace` | yes | Similarity match anchored on `context_before`/`context_after` |
| `replace_by_line` | yes | Replace an inclusive `line_start`..`line_end` range |
| `insert` | yes | Insert `content` after `line_start` |
| `delete` | yes | Delete an inclusive line range |
| `smart_replace` | yes | Replace when unique, otherwise list the candidates |
| `confirm_smart_replace` | yes | Replace the candidate with the given `match_id` |
| `create_file` | yes | Create a new file |
| `delete_file` | yes | Delete a file, after backing it up |
| `undo` | yes | Restore a file from its most recent backup |

### Choosing a replace action

* `str_replace` is the default: it refuses ambiguous and missing matches.
* `surgical_replace` when the model cannot reproduce indentation or line wrapping.
* `context_replace` when the block appears several times and only the surroundings
  tell them apart; it reports a confidence and refuses weak matches.
* `replace_by_line` after a `view`, when nothing else fits.

## Safety

* Every path is resolved inside the workspace root; `..` and absolute paths elsewhere
  are refused.
* Every write is preceded by a timestamped copy in `.tules_backups/`, mirroring the
  project layout. `undo` restores the newest one.
* An edit that would leave a `.py` file unparseable is refused, and the reply carries
  the syntax error plus the lines around it.
* Line endings are preserved: a CRLF file stays CRLF.
* After a successful edit the file is reviewed and any new issue is attached to the
  reply as a warning.
* `run` executes arbitrary shell commands. Start with `--no-shell` if you do not want
  the model to have that.

## Layout

```
tules/
  agent.py        dispatch, auto review
  registry.py     action name -> handler
  commands/       one module per family of actions
  editor.py       every write, backup and syntax guard
  matching.py     normalization and fuzzy block location
  search.py       text, regex, fuzzy and filename search
  analysis.py     symbols, review, duplicates, dependents
  workspace.py    path resolution, reads, writes, backups
  protocol.py     clipboard payload -> commands
  formatting.py   results -> the plain text reply
  monitor.py      the clipboard loop
  cli.py          argument parsing
tests/            pytest suite
```

## Tests

```sh
pip install -e ".[dev]"
pytest
```
