#!/usr/bin/env python3
"""
TULES (Terminal Utility for Local Editing & Search)
An insanely powerful local AI code agent that operates via clipboard monitoring.
"""

import os
import sys
import re
import json
import ast
import difflib
import shutil
import time
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime

try:
    import pyperclip
except ImportError:
    print("ERROR: 'pyperclip' is required. Install it via: pip install pyperclip")
    sys.exit(1)

# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class SearchResult:
    file_path: str
    line_number: int
    content: str
    context_before: str = ""
    context_after: str = ""
    match_type: str = "exact"

@dataclass
class EditOperation:
    file_path: str
    operation_type: str
    old_content: str = ""
    new_content: str = ""
    line_start: int = 0
    line_end: int = 0
    reason: str = ""

@dataclass
class CommandResult:
    success: bool
    message: str
    details: Dict = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

# ==============================================================================
# UTILITIES
# ==============================================================================

def play_beep():
    import platform
    try:
        if platform.system() == 'Windows':
            import winsound
            winsound.Beep(1000, 150)
        elif platform.system() == 'Darwin':
            os.system('afplay /System/Library/Sounds/Ping.aiff')
        else:
            sys.stdout.write('\a')
            sys.stdout.flush()
    except Exception:
        sys.stdout.write('\a')
        sys.stdout.flush()

def safe_copy_to_clipboard(text: str) -> bool:
    try:
        pyperclip.copy(text)
        return True
    except Exception as e:
        print(f"[!] Failed to copy to clipboard: {e}")
        return False

# ==============================================================================
# CORE CLASSES
# ==============================================================================

class CodeAnalyzer:
    def __init__(self):
        self.language_patterns = {
            '.py': {'comment': r'#.*$', 'indent': '    '},
            '.js': {'comment': r'//.*$|/\*.*?\*/'},
            '.java': {'comment': r'//.*$|/\*.*?\*/'},
            '.cpp': {'comment': r'//.*$|/\*.*?\*/'},
        }
    
    def get_file_language(self, filepath: str) -> str:
        ext = Path(filepath).suffix.lower()
        return ext if ext in self.language_patterns else 'unknown'
    
    def analyze_structure(self, filepath: str) -> Dict:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f: lines = f.readlines()
            analysis = {'total_lines': len(lines), 'blank_lines': sum(1 for line in lines if line.strip() == ''), 'comment_lines': 0, 'code_lines': 0, 'functions': [], 'classes': [], 'imports': []}
            lang = self.get_file_language(filepath)
            comment_pattern = self.language_patterns.get(lang, {}).get('comment', '')
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if comment_pattern and re.match(comment_pattern, stripped): analysis['comment_lines'] += 1
                elif stripped: analysis['code_lines'] += 1
                if re.match(r'def\s+\w+', stripped) or re.match(r'(public|private|protected)?\s*\w+\s+\w+\(', stripped): analysis['functions'].append({'line': i, 'content': stripped})
                if re.match(r'class\s+\w+', stripped): analysis['classes'].append({'line': i, 'content': stripped})
                if re.match(r'(import|from)\s+', stripped) or re.match(r'#include', stripped): analysis['imports'].append({'line': i, 'content': stripped})
            return analysis
        except Exception as e: return {'error': str(e)}

class SmartSearcher:
    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir).resolve()
        self.include_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.hpp', '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.md', '.txt', '.sql', '.sh', '.bash', '.rb', '.go', '.rs', '.swift'}
        self.exclude_dirs = {'__pycache__', '.git', 'node_modules', 'venv', '.venv', 'env', '.env', 'dist', 'build', '.idea', '.vscode', 'target', 'bin', 'obj', '.DS_Store', '.tules_backups'}
    
    def should_include_file(self, filepath: Path) -> bool:
        if not filepath.is_file() or filepath.suffix.lower() not in self.include_extensions: return False
        return not any(part in self.exclude_dirs for part in filepath.parts)
    
    def search_exact(self, pattern: str, case_sensitive: bool = False, whole_word: bool = False) -> List[SearchResult]:
        results = []
        for filepath in self.root_dir.rglob('*'):
            if not self.should_include_file(filepath): continue
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f: lines = f.readlines()
                for i, line in enumerate(lines, 1):
                    search_line = line if case_sensitive else line.lower()
                    search_pattern = pattern if case_sensitive else pattern.lower()
                    if whole_word:
                        if re.search(r'\b' + re.escape(search_pattern) + r'\b', search_line): results.append(self._create_result(filepath, i, line, lines))
                    else:
                        if search_pattern in search_line: results.append(self._create_result(filepath, i, line, lines))
            except Exception: continue
        return results
    
    def search_regex(self, pattern: str) -> List[SearchResult]:
        results = []
        try: compiled_pattern = re.compile(pattern)
        except re.error: return []
        for filepath in self.root_dir.rglob('*'):
            if not self.should_include_file(filepath): continue
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f: lines = f.readlines()
                for i, line in enumerate(lines, 1):
                    if compiled_pattern.search(line):
                        res = self._create_result(filepath, i, line, lines)
                        res.match_type = "regex"
                        results.append(res)
            except Exception: continue
        return results
    
    def search_fuzzy(self, pattern: str, threshold: float = 0.8) -> List[SearchResult]:
        results = []
        for filepath in self.root_dir.rglob('*'):
            if not self.should_include_file(filepath): continue
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f: lines = f.readlines()
                for i, line in enumerate(lines, 1):
                    if difflib.SequenceMatcher(None, pattern, line.strip()).ratio() >= threshold:
                        res = self._create_result(filepath, i, line, lines)
                        res.match_type = "fuzzy"
                        results.append(res)
            except Exception: continue
        return results
    
    def _create_result(self, filepath: Path, line_num: int, line: str, all_lines: List[str]) -> SearchResult:
        start_idx = max(0, line_num - 3)
        end_idx = min(len(all_lines), line_num + 2)
        return SearchResult(file_path=str(filepath.relative_to(self.root_dir)), line_number=line_num, content=line.rstrip(), context_before=''.join(all_lines[start_idx:line_num-1]), context_after=''.join(all_lines[line_num:end_idx]))
    
    def search_files_by_name(self, pattern: str) -> List[str]:
        return [str(filepath.relative_to(self.root_dir)) for filepath in self.root_dir.rglob('*') if filepath.is_file() and pattern.lower() in filepath.name.lower()]

class SurgicalEditor:
    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir).resolve()
        self.backup_dir = self.root_dir / '.tules_backups'
        self.backup_dir.mkdir(exist_ok=True)
        self.analyzer = CodeAnalyzer()

    def _validate_python_syntax(self, content: str) -> Tuple[bool, str]:
        try: compile(content, '<string>', 'exec'); return True, "Syntax OK"
        except SyntaxError as e: return False, f"SyntaxError at line {e.lineno}, offset {e.offset}: {e.msg}"

    def _validate_and_save(self, full_path: Path, original: str, new_content: str, filepath: str, reason: str) -> CommandResult:
        if full_path.suffix == '.py':
            is_valid, msg = self._validate_python_syntax(new_content)
            if not is_valid: return CommandResult(success=False, message="SYNTAX_ERROR_PREVENTED: Your replacement would break the file. Save aborted.", errors=[msg], details={'hint': 'Fix the syntax in your "replace_with" block and try again.'})
        backup_path = self.create_backup(full_path)
        with open(full_path, 'w', encoding='utf-8') as f: f.write(new_content)
        return CommandResult(success=True, message=f"Surgically replaced in {filepath}", details={'backup_created': str(backup_path), 'reason': reason})

    def create_backup(self, filepath: Path) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        relative_path = filepath.relative_to(self.root_dir)
        backup_path = self.backup_dir / relative_path.parent / f"{filepath.stem}_{timestamp}{filepath.suffix}"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(filepath, backup_path)
        return str(backup_path)

    def surgical_replace(self, filepath: str, search: str, replace: str, reason: str = "Surgical edit") -> CommandResult:
        full_path = self.root_dir / filepath
        if not full_path.exists(): return CommandResult(success=False, message=f"File not found: {filepath}")
        try:
            with open(full_path, 'r', encoding='utf-8') as f: original_content = f.read()
        except Exception as e: return CommandResult(success=False, message=f"Cannot read file: {e}")

        # Stage 1: Exact Match
        if search in original_content:
            new_content = original_content.replace(search, replace, 1)
            return self._validate_and_save(full_path, original_content, new_content, filepath, reason)

        # Stage 1.5: Whitespace-Agnostic Match (Aider style)
        search_lines = [line.strip() for line in search.split('\n') if line.strip()]
        if search_lines:
            orig_lines = original_content.split('\n')
            for i in range(len(orig_lines) - len(search_lines) + 1):
                match = True
                for j, s_line in enumerate(search_lines):
                    if orig_lines[i+j].strip() != s_line:
                        match = False
                        break
                if match:
                    orig_block = '\n'.join(orig_lines[i:i+len(search_lines)])
                    new_content = original_content.replace(orig_block, replace, 1)
                    return self._validate_and_save(full_path, original_content, new_content, filepath, "Whitespace-agnostic replace")

        # Stage 2: Flexible Whitespace Regex Match
        tokens = re.findall(r'\S+', search)
        if len(tokens) > 0:
            flexible_pattern = r'\s*'.join(re.escape(token) for token in tokens)
            flexible_pattern = r'(?m)^\s*' + flexible_pattern + r'\s*$'
            matches = list(re.finditer(flexible_pattern, original_content))
            if len(matches) == 1:
                match = matches[0]
                new_content = original_content[:match.start()] + replace + original_content[match.end():]
                return self._validate_and_save(full_path, original_content, new_content, filepath, reason)
            elif len(matches) > 1:
                line_num = original_content[:matches[0].start()].count('\n') + 1
                return CommandResult(success=False, message=f"AMBIGUOUS: Found {len(matches)} matches. Provide more context or use 'replace_by_line'.", details={'first_match_line': line_num})

        # Stage 3: AST-Based Match (Python only)
        if full_path.suffix == '.py':
            try:
                tree = ast.parse(original_content)
                func_match = re.search(r'def\s+([a-zA-Z0-9_]+)', search)
                class_match = re.search(r'class\s+([a-zA-Z0-9_]+)', search)
                target_name = func_match.group(1) if func_match else (class_match.group(1) if class_match else None)
                if target_name:
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == target_name:
                            old_segment = ast.get_source_segment(original_content, node)
                            if old_segment and old_segment in original_content:
                                new_content = original_content.replace(old_segment, replace, 1)
                                return self._validate_and_save(full_path, original_content, new_content, filepath, "AST-based replace")
            except Exception: pass

        return CommandResult(success=False, message="SEARCH_FAILED: Could not find the 'search' block. Use 'read_file' or 'replace_by_line'.")

    def replace_by_line(self, filepath: str, line_start: int, line_end: int, replace: str, reason: str = "Line-based replace") -> CommandResult:
        full_path = self.root_dir / filepath
        if not full_path.exists(): return CommandResult(success=False, message=f"File not found: {filepath}")
        try:
            with open(full_path, 'r', encoding='utf-8') as f: lines = f.readlines()
            start_idx = max(0, line_start - 1)
            end_idx = min(len(lines), line_end)
            new_lines = lines[:start_idx] + [replace + '\n' if not replace.endswith('\n') else replace] + lines[end_idx:]
            new_content = ''.join(new_lines)
            return self._validate_and_save(full_path, ''.join(lines), new_content, filepath, reason)
        except Exception as e: return CommandResult(success=False, message=f"Line replace failed: {str(e)}")

    # --- Legacy methods kept for insert/delete and old replace commands ---
    def validate_edit(self, operation: EditOperation) -> Tuple[bool, List[str]]:
        warnings, errors = [], []
        filepath = self.root_dir / operation.file_path
        if not filepath.exists(): errors.append(f"File does not exist: {operation.file_path}"); return False, errors
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f: current_content = f.read()
        except Exception as e: errors.append(f"Cannot read file: {e}"); return False, errors
        if operation.operation_type == 'replace' and operation.old_content and operation.old_content not in current_content: errors.append("Old content not found."); return False, errors
        return True, warnings + errors

    def execute_edit(self, operation: EditOperation) -> CommandResult:
        filepath = self.root_dir / operation.file_path
        is_valid, messages = self.validate_edit(operation)
        if not is_valid: return CommandResult(success=False, message="Edit validation failed", errors=messages)
        try:
            backup_path = self.create_backup(filepath)
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f: current_content = f.read()
            if operation.operation_type == 'replace': new_content = current_content.replace(operation.old_content, operation.new_content, 1) if operation.old_content else operation.new_content
            elif operation.operation_type == 'insert':
                lines = current_content.split('\n'); lines.insert(min(operation.line_start, len(lines)), operation.new_content); new_content = '\n'.join(lines)
            elif operation.operation_type == 'delete':
                lines = current_content.split('\n'); del lines[max(0, operation.line_start - 1):min(operation.line_end, len(lines))]; new_content = '\n'.join(lines)
            else: return CommandResult(success=False, message=f"Unknown operation type: {operation.operation_type}")
            
            if filepath.suffix == '.py':
                is_valid, msg = self._validate_python_syntax(new_content)
                if not is_valid: return CommandResult(success=False, message="SYNTAX_ERROR_PREVENTED", errors=[msg])

            with open(filepath, 'w', encoding='utf-8') as f: f.write(new_content)
            return CommandResult(success=True, message=f"Successfully {operation.operation_type}d in {operation.file_path}", details={'backup_created': backup_path, 'reason': operation.reason}, warnings=messages)
        except Exception as e: return CommandResult(success=False, message=f"Edit failed: {str(e)}", errors=[str(e)])

class TulesAgent:
    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir).resolve()
        self.searcher = SmartSearcher(str(self.root_dir))
        self.editor = SurgicalEditor(str(self.root_dir))
        print(f"TULES Agent initialized. Working directory: {self.root_dir}")
    
    def execute_single_command(self, cmd: Dict) -> CommandResult:
        action = cmd.get('action', '').lower()
        try:
            if action == 'read_file': return self._handle_read_file(cmd)
            elif action == 'search': return self._handle_search(cmd)
            elif action == 'search_regex': return self._handle_search_regex(cmd)
            elif action == 'search_fuzzy': return self._handle_search_fuzzy(cmd)
            elif action == 'replace': return self._handle_replace(cmd)
            elif action == 'insert': return self._handle_insert(cmd)
            elif action == 'delete': return self._handle_delete(cmd)
            elif action == 'analyze': return self._handle_analyze(cmd)
            elif action == 'list_files': return self._handle_list_files(cmd)
            elif action == 'run': return self._handle_run(cmd)
            elif action == 'create_file': return self._handle_create_file(cmd)
            elif action == 'delete_file': return self._handle_delete_file(cmd)
            elif action == 'search_and_replace_all': return self._handle_search_and_replace_all(cmd)
            elif action == 'smart_replace': return self._handle_smart_replace(cmd)
            elif action == 'confirm_smart_replace': return self._handle_confirm_smart_replace(cmd)
            elif action == 'extract_symbols': return self._handle_extract_symbols(cmd)
            elif action == 'memory': return self._handle_memory(cmd)
            elif action == 'help': return self._handle_help(cmd)
            elif action == 'surgical_replace': return self._handle_surgical_replace(cmd)
            elif action == 'replace_by_line': return self._handle_replace_by_line(cmd)
            elif action == 'view': return self._handle_view(cmd)
            elif action == 'str_replace': return self._handle_str_replace(cmd)
            else: return CommandResult(success=False, message=f"Unknown action: {action}")
        except Exception as e: return CommandResult(success=False, message=f"Execution error: {str(e)}", errors=[str(e)])

    def _handle_read_file(self, cmd: Dict) -> CommandResult:
        filepath = cmd.get('file', '')
        if not filepath: return CommandResult(success=False, message="Missing file path")
        full_path = self.root_dir / filepath
        if not full_path.exists(): return CommandResult(success=False, message=f"File not found: {filepath}")
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f: lines = f.readlines()
            start_line = cmd.get('start_line'); end_line = cmd.get('end_line')
            if start_line is not None and end_line is not None:
                start_idx = max(0, int(start_line) - 1); end_idx = min(len(lines), int(end_line))
                content = ''.join(lines[start_idx:end_idx]); message = f"Read lines {start_line} to {end_line} of {filepath}"
            else: content = ''.join(lines); message = f"Read {filepath}"
            return CommandResult(success=True, message=message, details={'content': content, 'length': len(content), 'total_lines': len(lines)})
        except Exception as e: return CommandResult(success=False, message=f"Failed to read: {str(e)}")

    def _handle_search(self, cmd: Dict) -> CommandResult:
        results = self.searcher.search_exact(cmd.get('search', ''), cmd.get('case_sensitive', False), cmd.get('whole_word', False))
        return CommandResult(success=True, message=f"Found {len(results)} matches", details={'matches': [{'file': r.file_path, 'line': r.line_number, 'content': r.content[:100]} for r in results[:20]]})

    def _handle_search_regex(self, cmd: Dict) -> CommandResult:
        results = self.searcher.search_regex(cmd.get('search', ''))
        return CommandResult(success=True, message=f"Found {len(results)} regex matches", details={'matches': [{'file': r.file_path, 'line': r.line_number, 'content': r.content[:100]} for r in results[:20]]})

    def _handle_search_fuzzy(self, cmd: Dict) -> CommandResult:
        results = self.searcher.search_fuzzy(cmd.get('search', ''), float(cmd.get('threshold', 0.8)))
        return CommandResult(success=True, message=f"Found {len(results)} fuzzy matches", details={'matches': [{'file': r.file_path, 'line': r.line_number, 'content': r.content[:100]} for r in results[:20]]})

    def _handle_replace(self, cmd: Dict) -> CommandResult:
        op = EditOperation(file_path=cmd.get('file', ''), operation_type='replace', old_content=cmd.get('search', ''), new_content=cmd.get('replace_with', ''), reason=cmd.get('reason', 'AI edit'))
        return self.editor.execute_edit(op)

    def _handle_insert(self, cmd: Dict) -> CommandResult:
        op = EditOperation(file_path=cmd.get('file', ''), operation_type='insert', new_content=cmd.get('content', ''), line_start=cmd.get('line_start', 0), reason=cmd.get('reason', 'AI edit'))
        return self.editor.execute_edit(op)

    def _handle_delete(self, cmd: Dict) -> CommandResult:
        op = EditOperation(file_path=cmd.get('file', ''), operation_type='delete', line_start=cmd.get('line_start', 0), line_end=cmd.get('line_end', 0), reason=cmd.get('reason', 'AI edit'))
        return self.editor.execute_edit(op)

    def _handle_analyze(self, cmd: Dict) -> CommandResult:
        filepath = cmd.get('file', '')
        if filepath:
            full_path = self.root_dir / filepath
            if not full_path.exists(): return CommandResult(success=False, message=f"File not found: {filepath}")
            return CommandResult(success=True, message=f"Analyzed {filepath}", details=self.editor.analyzer.analyze_structure(str(full_path)))
        return CommandResult(success=True, message="Project analysis complete", details=self._analyze_project())

    def _analyze_project(self) -> Dict:
        analysis = {'total_files': 0, 'files_by_type': {}, 'total_lines': 0}
        for filepath in self.root_dir.rglob('*'):
            if filepath.is_file() and self.searcher.should_include_file(filepath):
                analysis['total_files'] += 1; ext = filepath.suffix.lower()
                analysis['files_by_type'][ext] = analysis['files_by_type'].get(ext, 0) + 1
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f: analysis['total_lines'] += len(f.readlines())
                except: pass
        return analysis

    def _handle_list_files(self, cmd: Dict) -> CommandResult:
        matches = self.searcher.search_files_by_name(cmd.get('pattern', '*'))
        return CommandResult(success=True, message=f"Found {len(matches)} files", details={'files': matches})

    def _handle_run(self, cmd: Dict) -> CommandResult:
        command_str = cmd.get('command', '')
        if not command_str: return CommandResult(success=False, message="Missing 'command'")
        try:
            result = subprocess.run(command_str, shell=True, capture_output=True, text=True, timeout=30)
            return CommandResult(success=(result.returncode == 0), message=f"Return code {result.returncode}", details={'stdout': result.stdout[-2000:], 'stderr': result.stderr[-2000:]})
        except subprocess.TimeoutExpired: return CommandResult(success=False, message="Command timed out")
        except Exception as e: return CommandResult(success=False, message=f"Execution failed: {str(e)}")

    def _handle_smart_replace(self, cmd: Dict) -> CommandResult:
        filepath = cmd.get('file', ''); search_str = cmd.get('search', ''); replace_str = cmd.get('replace_with', '')
        if not filepath or not search_str: return CommandResult(success=False, message="Missing 'file' or 'search'")
        full_path = self.root_dir / filepath
        if not full_path.exists(): return CommandResult(success=False, message=f"File not found: {filepath}")
        try:
            with open(full_path, 'r', encoding='utf-8') as f: content = f.read()
            matches = []; start = 0
            while True:
                idx = content.find(search_str, start)
                if idx == -1: break
                line_num = content[:idx].count('\n') + 1; lines = content.split('\n')
                ctx_start = max(0, line_num - 4); ctx_end = min(len(lines), line_num + 3)
                matches.append({'id': len(matches), 'line': line_num, 'context': '\n'.join(lines[ctx_start:ctx_end])})
                start = idx + len(search_str)
            if len(matches) == 0: return CommandResult(success=False, message="Search string not found.")
            if len(matches) == 1:
                new_content = content.replace(search_str, replace_str, 1); backup_path = self.editor.create_backup(full_path)
                with open(full_path, 'w', encoding='utf-8') as f: f.write(new_content)
                return CommandResult(success=True, message=f"Auto-replaced 1 match", details={'backup': backup_path})
            return CommandResult(success=False, message=f"AMBIGUOUS: Found {len(matches)} matches.", details={'matches': matches})
        except Exception as e: return CommandResult(success=False, message=f"Failed: {str(e)}")

    def _handle_confirm_smart_replace(self, cmd: Dict) -> CommandResult:
        filepath = cmd.get('file', ''); search_str = cmd.get('search', ''); replace_str = cmd.get('replace_with', ''); match_id = cmd.get('match_id', 0)
        full_path = self.root_dir / filepath
        if not full_path.exists(): return CommandResult(success=False, message=f"File not found: {filepath}")
        try:
            with open(full_path, 'r', encoding='utf-8') as f: content = f.read()
            start = 0; target_idx = -1
            for i in range(match_id + 1):
                idx = content.find(search_str, start)
                if idx == -1: return CommandResult(success=False, message=f"Match ID {match_id} not found.")
                if i == match_id: target_idx = idx; break
                start = idx + len(search_str)
            new_content = content[:target_idx] + replace_str + content[target_idx + len(search_str):]
            backup_path = self.editor.create_backup(full_path)
            with open(full_path, 'w', encoding='utf-8') as f: f.write(new_content)
            return CommandResult(success=True, message=f"Replaced match ID {match_id}", details={'backup': backup_path})
        except Exception as e: return CommandResult(success=False, message=f"Failed: {str(e)}")

    def _handle_extract_symbols(self, cmd: Dict) -> CommandResult:
        filepath = cmd.get('file', '')
        if not filepath: return CommandResult(success=False, message="Missing 'file'")
        full_path = self.root_dir / filepath
        if not full_path.exists(): return CommandResult(success=False, message=f"File not found: {filepath}")
        ext = full_path.suffix.lower(); symbols = []
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
            if ext == '.py':
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        docstring = ast.get_docstring(node) or ""
                        symbols.append({'type': type(node).__name__, 'name': node.name, 'line': node.lineno, 'docstring': docstring[:100]})
            elif ext in ['.js', '.ts']:
                for match in re.finditer(r'(?:class|function|const|let|var)\s+([a-zA-Z0-9_]+)', content):
                    line_num = content[:match.start()].count('\n') + 1
                    symbols.append({'type': 'JS/TS Symbol', 'name': match.group(1), 'line': line_num, 'docstring': ''})
            return CommandResult(success=True, message=f"Extracted {len(symbols)} symbols", details={'symbols': symbols})
        except Exception as e: return CommandResult(success=False, message=f"Failed to extract: {str(e)}")

    def _handle_memory(self, cmd: Dict) -> CommandResult:
        action_type = cmd.get('action_type', ''); content = cmd.get('content', ''); target = cmd.get('target', 'scratchpad')
        tules_dir = self.root_dir / '.tules'; tules_dir.mkdir(exist_ok=True)
        filename = 'scratchpad.md' if target == 'scratchpad' else 'todo.md'; filepath = tules_dir / filename
        try:
            if action_type == 'write':
                with open(filepath, 'a', encoding='utf-8') as f: f.write(content + '\n')
                return CommandResult(success=True, message=f"Appended to {filename}")
            elif action_type == 'read':
                if not filepath.exists(): return CommandResult(success=True, message=f"{filename} is empty.", details={'content': ''})
                with open(filepath, 'r', encoding='utf-8') as f: return CommandResult(success=True, message=f"Read {filename}", details={'content': f.read()})
            else: return CommandResult(success=False, message="action_type must be 'write' or 'read'")
        except Exception as e: return CommandResult(success=False, message=f"Memory failed: {str(e)}")

    def _handle_help(self, cmd: Dict) -> CommandResult:
        help_text = "Actions: read_file, search, search_regex, search_fuzzy, replace, insert, delete, analyze, list_files, run, create_file, delete_file, search_and_replace_all, smart_replace, confirm_smart_replace, extract_symbols, memory, surgical_replace, replace_by_line, help."
        return CommandResult(success=True, message="Available actions", details={'help': help_text})

    def _handle_surgical_replace(self, cmd: Dict) -> CommandResult:
        return self.editor.surgical_replace(filepath=cmd.get('file', ''), search=cmd.get('search', ''), replace=cmd.get('replace_with', ''), reason=cmd.get('reason', 'Surgical AI edit'))

    def _handle_replace_by_line(self, cmd: Dict) -> CommandResult:
        return self.editor.replace_by_line(filepath=cmd.get('file', ''), line_start=int(cmd.get('line_start', 1)), line_end=int(cmd.get('line_end', 1)), replace=cmd.get('replace_with', ''), reason=cmd.get('reason', 'Line-based AI edit'))

    def _handle_view(self, cmd: Dict) -> CommandResult:
        filepath = cmd.get('file', '')
        full_path = self.root_dir / filepath
        if not full_path.exists(): return CommandResult(success=False, message=f"File not found: {filepath}")
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f: lines = f.readlines()
            numbered_lines = [f"{i+1:04} | {line.rstrip()}" for i, line in enumerate(lines)]
            content = "\n".join(numbered_lines)
            return CommandResult(success=True, message=f"Viewed {filepath} with line numbers", details={'content': content, 'total_lines': len(lines)})
        except Exception as e: return CommandResult(success=False, message=f"Failed to view: {str(e)}")

    def _handle_str_replace(self, cmd: Dict) -> CommandResult:
        filepath = cmd.get('file', '')
        old_str = cmd.get('old_str', '')
        new_str = cmd.get('new_str', '')
        if not filepath or not old_str: return CommandResult(success=False, message="Missing 'file' or 'old_str'")
        full_path = self.root_dir / filepath
        if not full_path.exists(): return CommandResult(success=False, message=f"File not found: {filepath}")
        try:
            with open(full_path, 'r', encoding='utf-8') as f: content = f.read()
            count = content.count(old_str)
            if count == 0: return CommandResult(success=False, message="NOT_FOUND: old_str not found. Use 'view' to get exact text.")
            if count > 1: return CommandResult(success=False, message=f"NOT_UNIQUE: old_str found {count} times. Provide more context or use 'view' + 'replace_by_line'.")
            new_content = content.replace(old_str, new_str, 1)
            if full_path.suffix == '.py':
                is_valid, msg = self.editor._validate_python_syntax(new_content)
                if not is_valid: return CommandResult(success=False, message="SYNTAX_ERROR_PREVENTED", errors=[msg])
            backup_path = self.editor.create_backup(full_path)
            with open(full_path, 'w', encoding='utf-8') as f: f.write(new_content)
            return CommandResult(success=True, message=f"Successfully replaced in {filepath}", details={'backup_created': str(backup_path)})
        except Exception as e: return CommandResult(success=False, message=f"Failed: {str(e)}")

    def _handle_create_file(self, cmd: Dict) -> CommandResult:
        filepath = cmd.get('file', ''); content = cmd.get('content', '')
        if not filepath: return CommandResult(success=False, message="Missing 'file'")
        full_path = self.root_dir / filepath
        if full_path.exists(): return CommandResult(success=False, message=f"File already exists: {filepath}")
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f: f.write(content)
            return CommandResult(success=True, message=f"Created {filepath}", details={'lines': len(content.split('\n'))})
        except Exception as e: return CommandResult(success=False, message=f"Failed: {str(e)}")

    def _handle_delete_file(self, cmd: Dict) -> CommandResult:
        filepath = cmd.get('file', '')
        if not filepath: return CommandResult(success=False, message="Missing 'file'")
        full_path = self.root_dir / filepath
        if not full_path.exists(): return CommandResult(success=False, message=f"File does not exist: {filepath}")
        try:
            backup_path = self.editor.create_backup(full_path); full_path.unlink()
            return CommandResult(success=True, message=f"Deleted {filepath}", details={'backup_created': backup_path})
        except Exception as e: return CommandResult(success=False, message=f"Failed: {str(e)}")

    def _handle_search_and_replace_all(self, cmd: Dict) -> CommandResult:
        filepath = cmd.get('file', ''); search_str = cmd.get('search', ''); replace_str = cmd.get('replace_with', '')
        if not filepath or not search_str: return CommandResult(success=False, message="Missing 'file' or 'search'")
        full_path = self.root_dir / filepath
        if not full_path.exists(): return CommandResult(success=False, message=f"File does not exist: {filepath}")
        try:
            with open(full_path, 'r', encoding='utf-8') as f: content = f.read()
            if search_str not in content: return CommandResult(success=False, message="Search string not found")
            count = content.count(search_str); new_content = content.replace(search_str, replace_str)
            backup_path = self.editor.create_backup(full_path)
            with open(full_path, 'w', encoding='utf-8') as f: f.write(new_content)
            return CommandResult(success=True, message=f"Replaced {count} occurrences", details={'backup_created': backup_path, 'occurrences': count})
        except Exception as e: return CommandResult(success=False, message=f"Failed: {str(e)}")

# ==============================================================================
# CLIPBOARD MONITOR
# ==============================================================================

class ClipboardMonitor:
    def __init__(self, agent: TulesAgent):
        self.agent = agent
        self.last_clipboard = ""
        self.running = True

    def start(self):
        print("\n" + "="*60)
        print(" TULES Clipboard Monitor Active (FULL SURGICAL MODE)")
        print(" Waiting for 'edit:' ... 'endedit' commands...")
        print(" Press Ctrl+C to stop.")
        print("="*60 + "\n")
        try:
            while self.running:
                current = pyperclip.paste()
                if current != self.last_clipboard:
                    self.last_clipboard = current
                    self.process_clipboard(current)
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nTULES Monitor stopped.")

    def process_clipboard(self, text: str):
        pattern = r'(?is)(?:```[a-zA-Z]*\s*)?edit:\s*(.*?)\s*endedit(?:\s*```)?'
        match = re.search(pattern, text)
        if match:
            json_payload = match.group(1).strip()
            json_payload = re.sub(r'^["\']{3}|["\']{3}$', '', json_payload).strip()
            print("\n[!] TULES Command Detected! Executing...")
            self.execute_command(json_payload)

    def _extract_json_robust(self, text: str) -> Optional[str]:
        start_arr = text.find('[')
        end_arr = text.rfind(']')
        if start_arr != -1 and end_arr > start_arr: return text[start_arr:end_arr+1]
        start_obj = text.find('{')
        end_obj = text.rfind('}')
        if start_obj != -1 and end_obj > start_obj: return text[start_obj:end_obj+1]
        return None

    def execute_command(self, json_payload: str):
        try:
            parsed_data = json.loads(json_payload)
        except json.JSONDecodeError:
            cleaned_payload = self._extract_json_robust(json_payload)
            if cleaned_payload:
                cleaned_payload = re.sub(r'(?<!\\)\n', '\\n', cleaned_payload)
                try:
                    parsed_data = json.loads(cleaned_payload)
                    print("[*] Successfully extracted JSON using robust depth-tracker.")
                except json.JSONDecodeError as e:
                    error_msg = f"STATUS: FAILED\nMESSAGE: Invalid JSON even after robust cleaning.\nDETAILS: {str(e)}"
                    safe_copy_to_clipboard(error_msg); play_beep(); return
            else:
                error_msg = "STATUS: FAILED\nMESSAGE: Could not find any JSON object or array in payload."
                safe_copy_to_clipboard(error_msg); play_beep(); return
        
        try:
            commands = [parsed_data] if isinstance(parsed_data, dict) else parsed_data
            if not isinstance(commands, list): raise ValueError("JSON must be an object or array.")
            
            results = [self.agent.execute_single_command(cmd) for cmd in commands]
            output = self.format_result(results[0]) if len(results) == 1 else self.format_batch_results(results)
            
            if safe_copy_to_clipboard(output):
                play_beep()
                print("[*] Result copied to clipboard and beep played.")
            else:
                print(output)
        except Exception as e:
            error_msg = f"STATUS: FAILED\nMESSAGE: Execution failed.\nDETAILS: {str(e)}"
            safe_copy_to_clipboard(error_msg); play_beep()

    def format_result(self, result: CommandResult) -> str:
        lines = [f"STATUS: {'SUCCESS' if result.success else 'FAILED'}", f"MESSAGE: {result.message}"]
        if result.details:
            lines.append("DETAILS:")
            for key, value in result.details.items():
                if key == 'content' and isinstance(value, str):
                    lines.append(f"  {key}:")
                    lines.extend([f"    {line}" for line in value.split('\n')[:50]]) 
                elif isinstance(value, list):
                    lines.append(f"  {key}: {len(value)} items")
                    for item in value[:10]:
                        if isinstance(item, dict): lines.append(f"    - {item.get('file', 'N/A')}:{item.get('line', 'N/A')} | {str(item.get('content', ''))[:60]}...")
                        else: lines.append(f"    - {str(item)[:80]}")
                elif isinstance(value, str) and len(value) > 300: lines.append(f"  {key}: {value[:300]}... (truncated)")
                else: lines.append(f"  {key}: {value}")
        if result.warnings: lines.extend(["WARNINGS:"] + [f"  - {w}" for w in result.warnings])
        if result.errors: lines.extend(["ERRORS:"] + [f"  - {e}" for e in result.errors])
        return "\n".join(lines)

    def format_batch_results(self, results: List[CommandResult]) -> str:
        total = len(results); successful = sum(1 for r in results if r.success)
        lines = [f"BATCH EXECUTION COMPLETE", f"TOTAL: {total} | SUCCESS: {successful} | FAILED: {total - successful}", "=" * 60]
        for i, result in enumerate(results, 1):
            lines.append(f"\n[COMMAND {i}/{total}] STATUS: {'SUCCESS' if result.success else 'FAILED'}")
            lines.append(f"MESSAGE: {result.message}")
            if result.errors: lines.extend(["ERRORS:"] + [f"  - {e}" for e in result.errors])
        return "\n".join(lines)

def main():
    root_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    agent = TulesAgent(root_dir=root_dir)
    monitor = ClipboardMonitor(agent)
    monitor.start()

if __name__ == "__main__":
    main()