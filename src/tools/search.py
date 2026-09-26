"""Repository exploration tools: list_files, find_files, grep, symbol_search."""

import fnmatch
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List

from .base import BaseTool, ToolCategory, ToolMetadata, ToolOutcome, ToolResult, SecurityManager


class ListFilesTool(BaseTool):
    """Lists files in the repository or a specific subdirectory."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="list_files",
            category=ToolCategory.EXPLORATION,
            description="List files and directories in the repository or given path.",
            parameters={
                "directory": {"type": "string", "default": ".", "description": "Subdirectory to list"},
                "max_files": {"type": "integer", "default": 100, "description": "Maximum number of files to return"},
                "recursive": {"type": "boolean", "default": False, "description": "List files recursively"}
            },
            estimated_token_cost=250,
            estimated_time_ms=80,
            risk=0.01,
            capabilities=["file-discovery", "structure-inspection"]
        )

    def execute(self, args: Dict[str, Any], workspace_dir: Path, security: SecurityManager) -> ToolResult:
        start_time = time.time()
        directory_str = args.get("directory", ".")
        max_files = args.get("max_files", 100)
        recursive = args.get("recursive", False)

        try:
            target_dir = security.validate_path(directory_str)
            if not target_dir.is_dir():
                return ToolResult(
                    tool_name=self.metadata.name,
                    success=False,
                    output=f"Error: '{directory_str}' is not a directory.",
                    outcome=ToolOutcome.FAILURE,
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    error_message="Path is not a directory."
                )

            entries = []
            new_files = []
            ignore_dirs = {".git", ".pytest_cache", "__pycache__", "node_modules", "target", "venv", ".venv"}

            if recursive:
                for root, dirs, files in os.walk(target_dir):
                    dirs[:] = [d for d in dirs if d not in ignore_dirs]
                    rel_root = Path(root).relative_to(target_dir)
                    for f in files:
                        rel_path = str(rel_root / f) if str(rel_root) != "." else f
                        entries.append(rel_path)
                        new_files.append(rel_path)
                        if len(entries) >= max_files:
                            break
                    if len(entries) >= max_files:
                        break
            else:
                for item in sorted(target_dir.iterdir()):
                    if item.name in ignore_dirs:
                        continue
                    suffix = "/" if item.is_dir() else ""
                    rel_name = item.name + suffix
                    entries.append(rel_name)
                    if not item.is_dir():
                        new_files.append(item.name)
                    if len(entries) >= max_files:
                        break

            output = "\n".join(entries) if entries else "No files found."
            output = security.truncate_output(output)
            tokens = self.estimate_tokens(output)
            duration_ms = int((time.time() - start_time) * 1000)

            outcome = ToolOutcome.HIGH_PROGRESS if entries else ToolOutcome.LOW_PROGRESS

            return ToolResult(
                tool_name=self.metadata.name,
                success=True,
                output=output,
                outcome=outcome,
                tokens_consumed=tokens,
                execution_time_ms=duration_ms,
                new_files=new_files,
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output=f"Error listing files: {str(e)}",
                outcome=ToolOutcome.FAILURE,
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=str(e),
            )


class FindFilesTool(BaseTool):
    """Finds files matching glob pattern."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="find_files",
            category=ToolCategory.EXPLORATION,
            description="Find files matching glob pattern (e.g. *.py, test_*.py, auth*.ts).",
            parameters={
                "pattern": {"type": "string", "required": True, "description": "Glob pattern to search for"},
                "directory": {"type": "string", "default": ".", "description": "Root directory for search"},
                "max_results": {"type": "integer", "default": 50, "description": "Max matching files"}
            },
            estimated_token_cost=300,
            estimated_time_ms=100,
            risk=0.01,
            capabilities=["pattern-search", "file-discovery"]
        )

    def execute(self, args: Dict[str, Any], workspace_dir: Path, security: SecurityManager) -> ToolResult:
        start_time = time.time()
        pattern = args.get("pattern", "*")
        directory_str = args.get("directory", ".")
        max_results = args.get("max_results", 50)

        try:
            target_dir = security.validate_path(directory_str)
            matches = []
            ignore_dirs = {".git", ".pytest_cache", "__pycache__", "node_modules", "target", "venv", ".venv"}

            for root, dirs, files in os.walk(target_dir):
                dirs[:] = [d for d in dirs if d not in ignore_dirs]
                rel_root = Path(root).relative_to(target_dir)
                for f in files:
                    if fnmatch.fnmatch(f, pattern) or fnmatch.fnmatch(str(rel_root / f), pattern):
                        rel_path = str(rel_root / f) if str(rel_root) != "." else f
                        matches.append(rel_path)
                        if len(matches) >= max_results:
                            break
                if len(matches) >= max_results:
                    break

            duration_ms = int((time.time() - start_time) * 1000)
            if matches:
                output = f"Found {len(matches)} files matching '{pattern}':\n" + "\n".join(matches)
                outcome = ToolOutcome.HIGH_PROGRESS
            else:
                output = f"No files matching '{pattern}' found."
                outcome = ToolOutcome.NO_PROGRESS

            output = security.truncate_output(output)
            tokens = self.estimate_tokens(output)

            return ToolResult(
                tool_name=self.metadata.name,
                success=True,
                output=output,
                outcome=outcome,
                tokens_consumed=tokens,
                execution_time_ms=duration_ms,
                new_files=matches,
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output=f"Error finding files: {str(e)}",
                outcome=ToolOutcome.FAILURE,
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=str(e),
            )


class GrepTool(BaseTool):
    """Searches text or regex in repository files."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="grep",
            category=ToolCategory.EXPLORATION,
            description="Search for a text pattern or regex in repository files.",
            parameters={
                "query": {"type": "string", "required": True, "description": "Text or regex pattern to search"},
                "path": {"type": "string", "default": ".", "description": "Path to search within"},
                "case_sensitive": {"type": "boolean", "default": False, "description": "Case sensitive match"},
                "file_pattern": {"type": "string", "default": "*", "description": "Glob filter for filenames"},
                "max_matches": {"type": "integer", "default": 50, "description": "Max line matches to return"}
            },
            estimated_token_cost=500,
            estimated_time_ms=120,
            risk=0.02,
            capabilities=["text-search", "code-discovery"]
        )

    def execute(self, args: Dict[str, Any], workspace_dir: Path, security: SecurityManager) -> ToolResult:
        start_time = time.time()
        query = args.get("query", "")
        path_str = args.get("path", ".")
        case_sensitive = args.get("case_sensitive", False)
        file_pattern = args.get("file_pattern", "*")
        max_matches = args.get("max_matches", 50)

        if not query:
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output="Error: Empty query for grep.",
                outcome=ToolOutcome.FAILURE,
                error_message="Empty query"
            )

        try:
            target_path = security.validate_path(path_str)
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                pattern = re.compile(query, flags)
            except re.error:
                pattern = re.compile(re.escape(query), flags)

            matched_lines = []
            matched_files = set()
            ignore_dirs = {".git", ".pytest_cache", "__pycache__", "node_modules", "target", "venv", ".venv"}

            files_to_search = []
            if target_path.is_file():
                files_to_search.append(target_path)
            else:
                for root, dirs, files in os.walk(target_path):
                    dirs[:] = [d for d in dirs if d not in ignore_dirs]
                    for f in files:
                        if fnmatch.fnmatch(f, file_pattern):
                            files_to_search.append(Path(root) / f)

            for file_path in files_to_search:
                rel_file = str(file_path.relative_to(workspace_dir))
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_idx, line in enumerate(f, 1):
                            if pattern.search(line):
                                matched_files.add(rel_file)
                                matched_lines.append(f"{rel_file}:{line_idx}: {line.rstrip()}")
                                if len(matched_lines) >= max_matches:
                                    break
                except Exception:
                    continue
                if len(matched_lines) >= max_matches:
                    break

            duration_ms = int((time.time() - start_time) * 1000)
            if matched_lines:
                output = f"Grep found {len(matched_lines)} matches across {len(matched_files)} files:\n" + "\n".join(matched_lines)
                outcome = ToolOutcome.HIGH_PROGRESS
            else:
                output = f"Grep found 0 matches for pattern '{query}'."
                outcome = ToolOutcome.NO_PROGRESS

            output = security.truncate_output(output)
            tokens = self.estimate_tokens(output)

            return ToolResult(
                tool_name=self.metadata.name,
                success=True,
                output=output,
                outcome=outcome,
                tokens_consumed=tokens,
                execution_time_ms=duration_ms,
                new_files=list(matched_files),
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output=f"Error during grep: {str(e)}",
                outcome=ToolOutcome.FAILURE,
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=str(e),
            )


class SymbolSearchTool(BaseTool):
    """Searches for functions, classes, methods, or symbols in repository source code."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="symbol_search",
            category=ToolCategory.EXPLORATION,
            description="Search for functions, classes, methods, variables, or type definitions.",
            parameters={
                "symbol": {"type": "string", "required": True, "description": "Symbol name or substring to search"},
                "symbol_type": {"type": "string", "default": "all", "description": "class, function, method, or all"}
            },
            estimated_token_cost=400,
            estimated_time_ms=110,
            risk=0.02,
            capabilities=["symbol-discovery", "ast-analysis"]
        )

    def execute(self, args: Dict[str, Any], workspace_dir: Path, security: SecurityManager) -> ToolResult:
        start_time = time.time()
        symbol = args.get("symbol", "")
        symbol_type = args.get("symbol_type", "all").lower()

        if not symbol:
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output="Error: Empty symbol provided.",
                outcome=ToolOutcome.FAILURE,
                error_message="Empty symbol"
            )

        try:
            results = []
            discovered_symbols = []
            files_found = set()

            # Regex patterns for Python, JS/TS, Rust definitions
            patterns = []
            if symbol_type in ("all", "class"):
                patterns.append((rf"^\s*class\s+([A-Za-z0-9_]*{re.escape(symbol)}[A-Za-z0-9_]*)", "class"))
                patterns.append((rf"^\s*struct\s+([A-Za-z0-9_]*{re.escape(symbol)}[A-Za-z0-9_]*)", "struct"))
            if symbol_type in ("all", "function", "method"):
                patterns.append((rf"^\s*(?:def|async def)\s+([A-Za-z0-9_]*{re.escape(symbol)}[A-Za-z0-9_]*)", "function"))
                patterns.append((rf"^\s*(?:function|const|let|var)\s+([A-Za-z0-9_]*{re.escape(symbol)}[A-Za-z0-9_]*)\s*=", "function"))
                patterns.append((rf"^\s*fn\s+([A-Za-z0-9_]*{re.escape(symbol)}[A-Za-z0-9_]*)", "function"))

            ignore_dirs = {".git", ".pytest_cache", "__pycache__", "node_modules", "target", "venv", ".venv"}
            for root, dirs, files in os.walk(workspace_dir):
                dirs[:] = [d for d in dirs if d not in ignore_dirs]
                for file_name in files:
                    ext = Path(file_name).suffix.lower()
                    if ext not in {".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go", ".c", ".cpp", ".h"}:
                        continue
                    full_path = Path(root) / file_name
                    rel_path = str(full_path.relative_to(workspace_dir))

                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            for idx, line in enumerate(f, 1):
                                for pat, kind in patterns:
                                    m = re.search(pat, line)
                                    if m:
                                        sym_name = m.group(1)
                                        discovered_symbols.append(sym_name)
                                        files_found.add(rel_path)
                                        results.append(f"{rel_path}:{idx} [{kind}] {sym_name} -> {line.strip()}")
                                        break
                                if len(results) >= 40:
                                    break
                    except Exception:
                        continue
                    if len(results) >= 40:
                        break

            duration_ms = int((time.time() - start_time) * 1000)
            if results:
                output = f"Symbol search found {len(results)} matches for '{symbol}':\n" + "\n".join(results)
                outcome = ToolOutcome.HIGH_PROGRESS
            else:
                output = f"No symbols matching '{symbol}' found."
                outcome = ToolOutcome.NO_PROGRESS

            output = security.truncate_output(output)
            tokens = self.estimate_tokens(output)

            return ToolResult(
                tool_name=self.metadata.name,
                success=True,
                output=output,
                outcome=outcome,
                tokens_consumed=tokens,
                execution_time_ms=duration_ms,
                new_files=list(files_found),
                new_symbols=discovered_symbols,
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output=f"Error in symbol search: {str(e)}",
                outcome=ToolOutcome.FAILURE,
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=str(e),
            )
