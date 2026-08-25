#!/usr/bin/env python3
"""Patch tules.py - fix the ClipboardMonitor skip_until bug + add debug logging."""

import re
import sys
from pathlib import Path
from datetime import datetime
import shutil

TARGET = Path("tules.py")

OLD_CLASS = '''class ClipboardMonitor:
    def __init__(self, agent: TulesAgent):
        self.agent = agent
        self.last_clipboard = ""
        self.running = True
        self.skip_until = 0

    def start(self):
        print("\\n" + "="*60)
        print(" TULES Clipboard Monitor Active (FULL SURGICAL MODE)")
        print(" Waiting for 'edit:' ... 'endedit' commands...")
        print(" Press Ctrl+C to stop.")
        print("="*60 + "\\n")
        try:
            while self.running:
                current = pyperclip.paste()
                if current != self.last_clipboard:
                    self.last_clipboard = current
                    if time.time() > self.skip_until:
                        self.process_clipboard(current)
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\\nTULES Monitor stopped.")'''

NEW_CLASS = '''class ClipboardMonitor:
    def __init__(self, agent: TulesAgent):
        self.agent = agent
        self.last_clipboard = ""
        self.running = True
        self.skip_until = 0

    def start(self):
        print("\\n" + "="*60)
        print(" TULES Clipboard Monitor Active (FULL SURGICAL MODE)")
        print(" Waiting for 'edit:' ... 'endedit' commands...")
        print(" Press Ctrl+C to stop.")
        print("="*60 + "\\n")
        try:
            while self.running:
                current = pyperclip.paste()
                if current != self.last_clipboard:
                    if time.time() > self.skip_until:
                        self.last_clipboard = current
                        self.process_clipboard(current)
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\\nTULES Monitor stopped.")'''

OLD_PROCESS = '''    def process_clipboard(self, text: str):
        pattern = r'(?is)(?:```[a-zA-Z]*\\s*)?edit:\\s*(.*?)\\s*endedit(?:\\s*```)?'
        match = re.search(pattern, text)
        if match:
            json_payload = match.group(1).strip()
            # Strip markdown code fences (backticks)
            json_payload = re.sub(r'^```[a-zA-Z]*\\s*', '', json_payload)
            json_payload = re.sub(r'\\s*```$', '', json_payload)
            json_payload = re.sub(r'^["\\']{3}|["\\']{3}$', '', json_payload).strip()
            print("\\n[!] TULES Command Detected! Executing...")
            self.execute_command(json_payload)'''

NEW_PROCESS = '''    def process_clipboard(self, text: str):
        pattern = r'(?is)(?:```[a-zA-Z]*\\s*)?edit:\\s*(.*?)\\s*endedit(?:\\s*```)?'
        match = re.search(pattern, text)
        if match:
            json_payload = match.group(1).strip()
            # Strip markdown code fences (backticks)
            json_payload = re.sub(r'^```[a-zA-Z]*\\s*', '', json_payload)
            json_payload = re.sub(r'\\s*```$', '', json_payload)
            json_payload = re.sub(r'^["\\']{3}|["\\']{3}$', '', json_payload).strip()
            print("\\n[!] TULES Command Detected! Executing...")
            self.execute_command(json_payload)
        else:
            if len(text.strip()) > 10:
                print(f"[TULES DEBUG] No edit/endedit pattern found. "
                      f"Clipboard starts with: {text[:120]!r}")'''


def main():
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found. Run this from the same directory.")
        sys.exit(1)

    content = TARGET.read_text(encoding="utf-8")

    # --- Backup ---
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = TARGET.with_suffix(f".{ts}.bak")
    shutil.copy2(TARGET, backup)
    print(f"Backup saved: {backup}")

    # --- Patch 1: fix start() ---
    if OLD_CLASS in content:
        content = content.replace(OLD_CLASS, NEW_CLASS, 1)
        print("[OK] Patched start() - skip_until race condition fixed")
    else:
        print("[SKIP] start() already patched or structure changed")

    # --- Patch 2: add debug logging to process_clipboard() ---
    if OLD_PROCESS in content:
        content = content.replace(OLD_PROCESS, NEW_PROCESS, 1)
        print("[OK] Patched process_clipboard() - debug logging added")
    else:
        print("[SKIP] process_clipboard() already patched or structure changed")

    TARGET.write_text(content, encoding="utf-8")
    print(f"\nDone. Run: python {TARGET}")


if __name__ == "__main__":
    main()