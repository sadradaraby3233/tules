# Smoke test area

A real end-to-end run of the browser automation: production code, a real
Chromium-family browser, and a fake AI chat website that behaves like one
(streaming responses, a Copy button, decoy buttons, a stop button).

## Run it

```sh
pip install "tules[browser]"
python smoke/run_smoke.py
```

The driver starts a local copy of `fake_ai_site.html`, launches a browser with
`--remote-debugging-port=9333`, and runs the same loop `tules --auto` runs:
bootstrap paste → Enter → completion detection → Copy click → clipboard read →
agent execution → reply paste → Enter → … until the AI replies without a
command block. It passes when the scripted AI's `replace` command actually
changed `hello.txt` in a temporary workspace after exactly two cycles.

Exit codes: `0` pass, `1` fail, `2` skipped (no browser found).

Useful flags:

| Flag | Purpose |
| --- | --- |
| `--headed` | show the browser window instead of running headless |
| `--keep` | leave the browser and site running for manual poking |
| `--browser PATH` | use a specific browser binary (or env `TULES_SMOKE_CHROME`) |
| `--port N` | remote debugging port (default 9333) |

The fake site also accepts query parameters for manual experiments:

- `?rate=40` — slow streaming (characters per second)
- `?latency=5000` — a long pause before the first character
- `?brokenCopy=1` — the first Copy click silently does nothing

## What this proves, and what the unit tests prove

The smoke run exercises the real CDP connection, page probes, element
recognition, fill-and-submit verification, completion detection, teach-free
element learning, mouse clicking, and clipboard hand-off in a real browser.
The pytest suite (`pytest -q`) covers the same loop plus every failure path —
stale selectors, teach flows, timeouts, clipboard failures, wrong Copy
buttons — against a simulated page, because those failures cannot be reliably
reproduced on demand in a live browser.
