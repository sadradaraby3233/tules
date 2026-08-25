#!/usr/bin/env python3
"""
TULES (Terminal Utility for Local Editing & Search)
An insanely powerful local AI code agent that operates via clipboard monitoring.
"""

import os
import sys
import re
import json
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
    """Plays a reliable native system beep."""
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
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            analysis = {
                'total_lines': len(lines),
                'blank_lines': sum(1 for line in lines if line.strip() == ''),
                'comment_lines': 0,
                'code_lines': 0,
                'functions': [],
                'classes': [],
                'imports': []
            }
            
            lang = self.get_file_language(filepath)
            patterns = self.language_patterns.get(lang, {})
            comment_pattern = patterns.get('comment', '')
            
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if comment_pattern and re.match(comment_pattern, stripped):
                    analysis['comment_lines'] += 1
                elif stripped:
                    analysis['code_lines'] += 1
                
                if re.match(r'def\s+\w+', stripped) or re.match(r'(public|private|protected)?\s*\w+\s+\w+\(', stripped):
                    analysis['functions'].append({'line': i, 'content': stripped})
                if re.match(r'class\s+\w+', stripped):
                    analysis['classes'].append({'line': i, 'content': stripped})
                if re.match(r'(import|from)\s+', stripped) or re.match(r'#include', stripped):
                    analysis['imports'].append({'line': i, 'content': stripped})
            
            return analysis
        except Exception as e:
            return {'error': str(e)}


class SmartSearcher:
    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir).resolve()
        self.include_extensions = {
            '.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.hpp',
            '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.md',
            '.txt', '.sql', '.sh', '.bash', '.rb', '.go', '.rs', '.swift'
        }
        self.exclude_dirs = {
            '__pycache__', '.git', 'node_modules', 'venv', '.venv',
            'env', '.env', 'dist', 'build', '.idea', '.vscode',
            'target', 'bin', 'obj', '.DS_Store'
        }
    
    def should_include_file(self, filepath: Path) -> bool:
        if not filepath.is_file() or filepath.suffix.lower() not in self.include_extensions:
            return False
        return not any(part in self.exclude_dirs for part in filepath.parts)
    
    def search_exact(self, pattern: str, case_sensitive: bool = False, whole_word: bool = False) -> List[SearchResult]:
        results = []
        for filepath in self.root_dir.rglob('*'):
            if not self.should_include_file(filepath):
                continue
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                for i, line in enumerate(lines, 1):
                    search_line = line if case_sensitive else line.lower()
                    search_pattern = pattern if case_sensitive else pattern.lower()
                    if whole_word:
                        if re.search(r'\b' + re.escape(search_pattern) + r'\b', search_line):
                            results.append(self._create_result(filepath, i, line, lines))
                    else:
                        if search_pattern in search_line:
                            results.append(self._create_result(filepath, i, line, lines))
            except Exception:
                continue
        return results
    
    def search_regex(self, pattern: str) -> List[SearchResult]:
        results = []
        try:
            compiled_pattern = re.compile(pattern)
        except re.error:
            return []
        
        for filepath in self.root_dir.rglob('*'):
            if not self.should_include_file(filepath):
                continue
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                for i, line in enumerate(lines, 1):
                    if compiled_pattern.search(line):
                        res = self._create_result(filepath, i, line, lines)
                        res.match_type = "regex"
                        results.append(res)
            except Exception:
                continue
        return results
    
    def search_fuzzy(self, pattern: str, threshold: float = 0.8) -> List[SearchResult]:
        results = []
        for filepath in self.root_dir.rglob('*'):
            if not self.should_include_file(filepath):
                continue
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                for i, line in enumerate(lines, 1):
                    if difflib.SequenceMatcher(None, pattern, line.strip()).ratio() >= threshold:
                        res = self._create_result(filepath, i, line, lines)
                        res.match_type = "fuzzy"
                        results.append(res)
            except Exception:
                continue
        return results
    
    def _create_result(self, filepath: Path, line_num: int, line: str, all_lines: List[str]) -> SearchResult:
        start_idx = max(0, line_num - 3)
        end_idx = min(len(all_lines), line_num + 2)
        return SearchResult(
            file_path=str(filepath.relative_to(self.root_dir)),
            line_number=line_num,
            content=line.rstrip(),
            context_before=''.join(all_lines[start_idx:line_num-1]),
            context_after=''.join(all_lines[line_num:end_idx])
        )
    
    def search_files_by_name(self, pattern: str) -> List[str]:
        return [str(filepath.relative_to(self.root_dir)) for filepath in self.root_dir.rglob('*') 
                if filepath.is_file() and pattern.lower() in filepath.name.lower()]


class SafeEditor:
    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir).resolve()
        self.backup_dir = self.root_dir / '.tules_backups'
        self.backup_dir.mkdir(exist_ok=True)
        self.analyzer = CodeAnalyzer()
    
    def validate_edit(self, operation: EditOperation) -> Tuple[bool, List[str]]:
        warnings, errors = [], []
        filepath = self.root_dir / operation.file_path
        
        if not filepath.exists():
            errors.append(f"File does not exist: {operation.file_path}")
            return False, errors
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                current_content = f.read()
        except Exception as e:
            errors.append(f"Cannot read file: {e}")
            return False, errors
        
        if operation.operation_type == 'replace' and operation.old_content and operation.old_content not in current_content:
            errors.append("Old content not found in file. Use 'read_file' to get exact content.")
            return False, errors
        
        if filepath.suffix in ['.py', '.js', '.java']:
            issues = self._check_syntax(filepath, current_content, operation)
            warnings.extend(issues)
        
        if operation.new_content and len(operation.new_content) > 100000:
            warnings.append("Large content change detected (>100KB)")
        
        return len(errors) == 0, warnings + errors
    
    def _check_syntax(self, filepath: Path, current_content: str, operation: EditOperation) -> List[str]:
        if filepath.suffix == '.py':
            temp_content = current_content
            if operation.operation_type == 'replace' and operation.old_content:
                temp_content = temp_content.replace(operation.old_content, operation.new_content, 1)
            try:
                compile(temp_content, str(filepath), 'exec')
            except SyntaxError as e:
                return [f"Syntax error would be introduced: {e}"]
        return []
    
    def create_backup(self, filepath: Path) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        relative_path = filepath.relative_to(self.root_dir)
        backup_path = self.backup_dir / relative_path.parent / f"{filepath.stem}_{timestamp}{filepath.suffix}"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(filepath, backup_path)
        return str(backup_path)
    
    def execute_edit(self, operation: EditOperation) -> CommandResult:
        filepath = self.root_dir / operation.file_path
        is_valid, messages = self.validate_edit(operation)
        if not is_valid:
            return CommandResult(success=False, message="Edit validation failed", errors=messages)
        
        try:
            backup_path = self.create_backup(filepath)
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                current_content = f.read()
            
            if operation.operation_type == 'replace':
                new_content = current_content.replace(operation.old_content, operation.new_content, 1) if operation.old_content else operation.new_content
            elif operation.operation_type == 'insert':
                lines = current_content.split('\n')
                lines.insert(min(operation.line_start, len(lines)), operation.new_content)
                new_content = '\n'.join(lines)
            elif operation.operation_type == 'delete':
                lines = current_content.split('\n')
                del lines[max(0, operation.line_start - 1):min(operation.line_end, len(lines))]
                new_content = '\n'.join(lines)
            else:
                return CommandResult(success=False, message=f"Unknown operation type: {operation.operation_type}")
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return CommandResult(
                success=True,
                message=f"Successfully {operation.operation_type}d in {operation.file_path}",
                details={'backup_created': backup_path, 'reason': operation.reason},
                warnings=messages
            )
        except Exception as e:
            return CommandResult(success=False, message=f"Edit failed: {str(e)}", errors=[str(e)])


class TulesAgent:
    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir).resolve()
        self.searcher = SmartSearcher(str(self.root_dir))
        self.editor = SafeEditor(str(self.root_dir))
        print(f"TULES Agent initialized. Working directory: {self.root_dir}")
    
    def execute_single_command(self, cmd: Dict) -> CommandResult:
        action = cmd.get('action', '').lower()
        try:
            if action == 'read_file':
                return self._handle_read_file(cmd)
            elif action == 'search':
                return self._handle_search(cmd)
            elif action == 'search_regex':
                return self._handle_search_regex(cmd)
            elif action == 'search_fuzzy':
                return self._handle_search_fuzzy(cmd)
            elif action == 'replace':
                return self._handle_replace(cmd)
            elif action == 'insert':
                return self._handle_insert(cmd)
            elif action == 'delete':
                return self._handle_delete(cmd)
            elif action == 'analyze':
                return self._handle_analyze(cmd)
            elif action == 'list_files':
                return self._handle_list_files(cmd)
            elif action == 'run':
                return self._handle_run(cmd)
            elif action == 'create_file':
                return self._handle_create_file(cmd)
            elif action == 'delete_file':
                return self._handle_delete_file(cmd)
            elif action == 'search_and_replace_all':
                return self._handle_search_and_replace_all(cmd)
            else:
                return CommandResult(success=False, message=f"Unknown action: {action}")
        except Exception as e:
            return CommandResult(success=False, message=f"Execution error: {str(e)}", errors=[str(e)])

    def _handle_read_file(self, cmd: Dict) -> CommandResult:
        filepath = cmd.get('file', '')
        if not filepath:
            return CommandResult(success=False, message="Missing file path")
        full_path = self.root_dir / filepath
        if not full_path.exists():
            return CommandResult(success=False, message=f"File not found: {filepath}")
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return CommandResult(success=True, message=f"Read {filepath}", details={'content': content, 'length': len(content)})
        except Exception as e:
            return CommandResult(success=False, message=f"Failed to read: {str(e)}")

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
            if not full_path.exists():
                return CommandResult(success=False, message=f"File not found: {filepath}")
            return CommandResult(success=True, message=f"Analyzed {filepath}", details=self.editor.analyzer.analyze_structure(str(full_path)))
        return CommandResult(success=True, message="Project analysis complete", details=self._analyze_project())

    def _analyze_project(self) -> Dict:
        analysis = {'total_files': 0, 'files_by_type': {}, 'total_lines': 0}
        for filepath in self.root_dir.rglob('*'):
            if filepath.is_file() and self.searcher.should_include_file(filepath):
                analysis['total_files'] += 1
                ext = filepath.suffix.lower()
                analysis['files_by_type'][ext] = analysis['files_by_type'].get(ext, 0) + 1
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        analysis['total_lines'] += len(f.readlines())
                except: pass
        return analysis

    def _handle_list_files(self, cmd: Dict) -> CommandResult:
        matches = self.searcher.search_files_by_name(cmd.get('pattern', '*'))
        return CommandResult(success=True, message=f"Found {len(matches)} files", details={'files': matches})

    def _handle_run(self, cmd: Dict) -> CommandResult:
        command_str = cmd.get('command', '')
        if not command_str:
            return CommandResult(success=False, message="Missing 'command' in run action")
        try:
            result = subprocess.run(command_str, shell=True, capture_output=True, text=True, timeout=30)
            return CommandResult(
                success=(result.returncode == 0),
                message=f"Command executed with return code {result.returncode}",
                details={
                    'stdout': result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout,
                    'stderr': result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr
                }
            )
        except subprocess.TimeoutExpired:
            return CommandResult(success=False, message="Command timed out after 30 seconds")
        except Exception as e:
            return CommandResult(success=False, message=f"Execution failed: {str(e)}")

    def _handle_create_file(self, cmd: Dict) -> CommandResult:
        filepath = cmd.get('file', '')
        content = cmd.get('content', '')
        if not filepath:
            return CommandResult(success=False, message="Missing 'file' in create_file action")
        full_path = self.root_dir / filepath
        if full_path.exists():
            return CommandResult(success=False, message=f"File already exists: {filepath}. Use 'replace' to modify it.")
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return CommandResult(success=True, message=f"Successfully created {filepath}", details={'lines': len(content.split('\n'))})
        except Exception as e:
            return CommandResult(success=False, message=f"Failed to create file: {str(e)}")

    def _handle_delete_file(self, cmd: Dict) -> CommandResult:
        filepath = cmd.get('file', '')
        if not filepath:
            return CommandResult(success=False, message="Missing 'file' in delete_file action")
        full_path = self.root_dir / filepath
        if not full_path.exists():
            return CommandResult(success=False, message=f"File does not exist: {filepath}")
        try:
            backup_path = self.editor.create_backup(full_path)
            full_path.unlink()
            return CommandResult(success=True, message=f"Successfully deleted {filepath}", details={'backup_created': backup_path})
        except Exception as e:
            return CommandResult(success=False, message=f"Failed to delete file: {str(e)}")

    def _handle_search_and_replace_all(self, cmd: Dict) -> CommandResult:
        filepath = cmd.get('file', '')
        search_str = cmd.get('search', '')
        replace_str = cmd.get('replace_with', '')
        if not filepath or not search_str:
            return CommandResult(success=False, message="Missing 'file' or 'search' in search_and_replace_all action")
        full_path = self.root_dir / filepath
        if not full_path.exists():
            return CommandResult(success=False, message=f"File does not exist: {filepath}")
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            if search_str not in content:
                return CommandResult(success=False, message="Search string not found in file")
            count = content.count(search_str)
            new_content = content.replace(search_str, replace_str)
            backup_path = self.editor.create_backup(full_path)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return CommandResult(success=True, message=f"Replaced {count} occurrences in {filepath}", details={'backup_created': backup_path, 'occurrences': count})
        except Exception as e:
            return CommandResult(success=False, message=f"Failed to replace all: {str(e)}")


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
        print(" TULES Clipboard Monitor Active")
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
        # Matches: edit:\n {json} \nendedit (case-insensitive, allows surrounding whitespace)
        pattern = r'(?is)^\s*edit:\s*(.*?)\s*endedit\s*$'
        match = re.search(pattern, text)
        if match:
            json_payload = match.group(1).strip()
            print("\n[!] TULES Command Detected! Executing...")
            self.execute_command(json_payload)

    def execute_command(self, json_payload: str):
        try:
            parsed_data = json.loads(json_payload)
            
            if isinstance(parsed_data, dict):
                commands = [parsed_data]
            elif isinstance(parsed_data, list):
                commands = parsed_data
            else:
                raise ValueError("JSON must be an object or an array of objects.")
            
            results = []
            for cmd in commands:
                result = self.agent.execute_single_command(cmd)
                results.append(result)
            
            if len(results) == 1:
                output = self.format_result(results[0])
            else:
                output = self.format_batch_results(results)
            
            if safe_copy_to_clipboard(output):
                play_beep()
                print("[*] Result copied to clipboard and beep played.")
            else:
                print(output)
                
        except json.JSONDecodeError as e:
            error_msg = f"STATUS: FAILED\nMESSAGE: Invalid JSON in command.\nDETAILS: {str(e)}\nPAYLOAD:\n{json_payload}"
            safe_copy_to_clipboard(error_msg)
            play_beep()
            print("[*] JSON Error copied to clipboard.")
        except Exception as e:
            error_msg = f"STATUS: FAILED\nMESSAGE: Execution failed.\nDETAILS: {str(e)}"
            safe_copy_to_clipboard(error_msg)
            play_beep()
            print("[*] Error copied to clipboard.")

    def format_result(self, result: CommandResult) -> str:
        lines = [f"STATUS: {'SUCCESS' if result.success else 'FAILED'}", f"MESSAGE: {result.message}"]
        if result.details:
            lines.append("DETAILS:")
            for key, value in result.details.items():
                if key == 'content' and isinstance(value, str):
                    lines.append(f"  {key}:")
                    file_lines = value.split('\n')
                    for line in file_lines:
                        lines.append(f"    {line}")
                elif isinstance(value, list):
                    lines.append(f"  {key}: {len(value)} items")
                    for item in value[:10]:
                        if isinstance(item, dict):
                            lines.append(f"    - {item.get('file', 'N/A')}:{item.get('line', 'N/A')} | {str(item.get('content', ''))[:60]}...")
                        else:
                            lines.append(f"    - {str(item)[:80]}")
                elif isinstance(value, str) and len(value) > 300:
                    lines.append(f"  {key}: {value[:300]}... (truncated)")
                else:
                    lines.append(f"  {key}: {value}")
        if result.warnings:
            lines.append("WARNINGS:")
            lines.extend([f"  - {w}" for w in result.warnings])
        if result.errors:
            lines.append("ERRORS:")
            lines.extend([f"  - {e}" for e in result.errors])
        return "\n".join(lines)

    def format_batch_results(self, results: List[CommandResult]) -> str:
        total = len(results)
        successful = sum(1 for r in results if r.success)
        failed = total - successful
        
        lines = [
            f"BATCH EXECUTION COMPLETE",
            f"TOTAL COMMANDS: {total}",
            f"SUCCESSFUL: {successful}",
            f"FAILED: {failed}",
            "=" * 60
        ]
        
        for i, result in enumerate(results, 1):
            lines.append(f"\n[COMMAND {i}/{total}] STATUS: {'SUCCESS' if result.success else 'FAILED'}")
            lines.append(f"MESSAGE: {result.message}")
            if result.details:
                lines.append("DETAILS:")
                for key, value in result.details.items():
                    if key == 'content' and isinstance(value, str):
                        lines.append(f"  {key}:")
                        file_lines = value.split('\n')
                        for line in file_lines:
                            lines.append(f"    {line}")
                    elif isinstance(value, list):
                        lines.append(f"  {key}: {len(value)} items")
                        for item in value[:10]:
                            if isinstance(item, dict):
                                lines.append(f"    - {item.get('file', 'N/A')}:{item.get('line', 'N/A')} | {str(item.get('content', ''))[:60]}...")
                            else:
                                lines.append(f"    - {str(item)[:80]}")
                    elif isinstance(value, str) and len(value) > 300:
                        lines.append(f"  {key}: {value[:300]}... (truncated)")
                    else:
                        lines.append(f"  {key}: {value}")
            if result.warnings:
                lines.append("WARNINGS:")
                lines.extend([f"  - {w}" for w in result.warnings])
            if result.errors:
                lines.append("ERRORS:")
                lines.extend([f"  - {e}" for e in result.errors])
                
        return "\n".join(lines)


def main():
    root_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    agent = TulesAgent(root_dir=root_dir)
    monitor = ClipboardMonitor(agent)
    monitor.start()

if __name__ == "__main__":
    main()