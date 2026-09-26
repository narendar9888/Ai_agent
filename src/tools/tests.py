"""Verification and code understanding tools: run_tests, run_build, dependency_search, call_graph."""

import ast
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Set

from .base import BaseTool, ToolCategory, ToolMetadata, ToolOutcome, ToolResult, SecurityManager


class RunTestsTool(BaseTool):
    """Runs repository test suite or targeted test cases."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="run_tests",
            category=ToolCategory.VERIFICATION,
            description="Run test suite or a targeted test (pytest, cargo test, npm test).",
            parameters={
                "target": {"type": "string", "default": "", "description": "Specific test file or test node e.g. tests/test_auth.py::test_login"},
                "framework": {"type": "string", "default": "auto", "description": "pytest, cargo, or npm"}
            },
            estimated_token_cost=1200,
            estimated_time_ms=3500,
            risk=0.05,
            capabilities=["verification", "failure-detection", "testing"]
        )

    def execute(self, args: Dict[str, Any], workspace_dir: Path, security: SecurityManager) -> ToolResult:
        start_time = time.time()
        target = args.get("target", "").strip()
        framework = args.get("framework", "auto").lower()

        # Determine test command
        cmd = []
        if framework == "auto":
            if (workspace_dir / "pytest.ini").exists() or (workspace_dir / "tests").exists() or list(workspace_dir.glob("test_*.py")):
                framework = "pytest"
            elif (workspace_dir / "Cargo.toml").exists():
                framework = "cargo"
            elif (workspace_dir / "package.json").exists():
                framework = "npm"
            else:
                framework = "pytest"

        if framework == "pytest":
            cmd = ["python3", "-m", "pytest", "-q"]
            if target:
                cmd.append(target)
        elif framework == "cargo":
            cmd = ["cargo", "test", "--quiet"]
            if target:
                cmd.extend(["--", target])
        elif framework == "npm":
            cmd = ["npm", "test", "--"]
            if target:
                cmd.append(target)
        else:
            cmd = ["python3", "-m", "pytest", "-q"]

        try:
            proc = subprocess.run(
                cmd,
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=security.timeout_seconds
            )
            duration_ms = int((time.time() - start_time) * 1000)

            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()
            output = f"Command: {' '.join(cmd)}\nExit Code: {proc.returncode}\n"
            if stdout:
                output += f"\nSTDOUT:\n{stdout}"
            if stderr:
                output += f"\nSTDERR:\n{stderr}"

            output = security.truncate_output(output)
            tokens = self.estimate_tokens(output)

            if proc.returncode == 0:
                outcome = ToolOutcome.VERIFICATION_SUCCESS
                success = True
            else:
                outcome = ToolOutcome.VERIFICATION_FAILURE
                success = False

            return ToolResult(
                tool_name=self.metadata.name,
                success=success,
                output=output,
                outcome=outcome,
                tokens_consumed=tokens,
                execution_time_ms=duration_ms,
                error_message=stderr if not success else None
            )
        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output=f"Test run timed out after {security.timeout_seconds} seconds.",
                outcome=ToolOutcome.FAILURE,
                execution_time_ms=duration_ms,
                error_message="Test timeout"
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output=f"Error executing test runner: {str(e)}",
                outcome=ToolOutcome.FAILURE,
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=str(e)
            )


class RunBuildTool(BaseTool):
    """Runs repository build or syntax compilation checks."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="run_build",
            category=ToolCategory.VERIFICATION,
            description="Run project build / syntax compilation check.",
            parameters={
                "command": {"type": "string", "default": "", "description": "Custom build command"}
            },
            estimated_token_cost=800,
            estimated_time_ms=2500,
            risk=0.05,
            capabilities=["build-verification", "syntax-check"]
        )

    def execute(self, args: Dict[str, Any], workspace_dir: Path, security: SecurityManager) -> ToolResult:
        start_time = time.time()
        custom_cmd = args.get("command", "").strip()

        if custom_cmd:
            cmd = custom_cmd
        elif (workspace_dir / "Cargo.toml").exists():
            cmd = "cargo check"
        elif (workspace_dir / "package.json").exists():
            cmd = "npm run build --if-present"
        elif (workspace_dir / "Makefile").exists():
            cmd = "make --dry-run"
        else:
            # Python syntax check on all .py files
            cmd = "python3 -m compileall -q ."

        try:
            parts = security.validate_command(cmd)
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=security.timeout_seconds
            )
            duration_ms = int((time.time() - start_time) * 1000)

            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()
            output = f"Build command: {cmd}\nExit code: {proc.returncode}\n"
            if stdout:
                output += f"\nSTDOUT:\n{stdout}"
            if stderr:
                output += f"\nSTDERR:\n{stderr}"

            output = security.truncate_output(output)
            tokens = self.estimate_tokens(output)

            success = (proc.returncode == 0)
            outcome = ToolOutcome.HIGH_PROGRESS if success else ToolOutcome.FAILURE

            return ToolResult(
                tool_name=self.metadata.name,
                success=success,
                output=output,
                outcome=outcome,
                tokens_consumed=tokens,
                execution_time_ms=duration_ms,
                error_message=stderr if not success else None
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output=f"Build failed with exception: {str(e)}",
                outcome=ToolOutcome.FAILURE,
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=str(e)
            )


class DependencySearchTool(BaseTool):
    """Finds imports and dependency relationships across project files."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="dependency_search",
            category=ToolCategory.UNDERSTANDING,
            description="Find imports and module dependencies for a given file or module name.",
            parameters={
                "module": {"type": "string", "required": True, "description": "Module or package name to search imports for"}
            },
            estimated_token_cost=400,
            estimated_time_ms=120,
            risk=0.01,
            capabilities=["dependency-analysis", "import-graph"]
        )

    def execute(self, args: Dict[str, Any], workspace_dir: Path, security: SecurityManager) -> ToolResult:
        start_time = time.time()
        module_name = args.get("module", "").strip()

        if not module_name:
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output="Error: No module name provided.",
                outcome=ToolOutcome.FAILURE,
                error_message="Missing module name"
            )

        try:
            results = []
            files_found = set()
            ignore_dirs = {".git", ".pytest_cache", "__pycache__", "node_modules", "target", "venv", ".venv"}

            for root, dirs, files in os.walk(workspace_dir):
                dirs[:] = [d for d in dirs if d not in ignore_dirs]
                for file_name in files:
                    if not file_name.endswith((".py", ".js", ".ts", ".rs")):
                        continue
                    full_path = Path(root) / file_name
                    rel_path = str(full_path.relative_to(workspace_dir))

                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            for idx, line in enumerate(f, 1):
                                if ("import " in line or "from " in line or "require(" in line or "use " in line) and module_name in line:
                                    results.append(f"{rel_path}:{idx}: {line.strip()}")
                                    files_found.add(rel_path)
                                    if len(results) >= 50:
                                        break
                    except Exception:
                        continue
                    if len(results) >= 50:
                        break

            duration_ms = int((time.time() - start_time) * 1000)
            if results:
                output = f"Found {len(results)} references to '{module_name}':\n" + "\n".join(results)
                outcome = ToolOutcome.HIGH_PROGRESS
            else:
                output = f"No import or dependency references found for '{module_name}'."
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
                new_files=list(files_found)
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output=f"Error searching dependencies: {str(e)}",
                outcome=ToolOutcome.FAILURE,
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=str(e)
            )


class CallGraphTool(BaseTool):
    """Finds callers and callees for a specified function in Python code."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="call_graph",
            category=ToolCategory.UNDERSTANDING,
            description="Find function callers and callees using static AST analysis.",
            parameters={
                "function_name": {"type": "string", "required": True, "description": "Target function name"}
            },
            estimated_token_cost=500,
            estimated_time_ms=150,
            risk=0.01,
            capabilities=["call-graph", "ast-analysis"]
        )

    def execute(self, args: Dict[str, Any], workspace_dir: Path, security: SecurityManager) -> ToolResult:
        start_time = time.time()
        func_name = args.get("function_name", "").strip()

        if not func_name:
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output="Error: No function_name provided.",
                outcome=ToolOutcome.FAILURE,
                error_message="Missing function_name"
            )

        try:
            callers = []
            callees = []
            files_scanned = 0

            ignore_dirs = {".git", ".pytest_cache", "__pycache__", "node_modules", "target", "venv", ".venv"}
            for root, dirs, files in os.walk(workspace_dir):
                dirs[:] = [d for d in dirs if d not in ignore_dirs]
                for f in files:
                    if f.endswith(".py"):
                        files_scanned += 1
                        file_path = Path(root) / f
                        rel_path = str(file_path.relative_to(workspace_dir))
                        try:
                            with open(file_path, "r", encoding="utf-8") as py_file:
                                tree = ast.parse(py_file.read(), filename=rel_path)

                            # Walk AST to find callers and callees
                            for node in ast.walk(tree):
                                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                    # If this function definition calls func_name, it's a caller
                                    for sub in ast.walk(node):
                                        if isinstance(sub, ast.Call):
                                            if isinstance(sub.func, ast.Name) and sub.func.id == func_name:
                                                callers.append(f"{rel_path}: {node.name}() calls {func_name}() (line {sub.lineno})")
                                            elif isinstance(sub.func, ast.Attribute) and sub.func.attr == func_name:
                                                callers.append(f"{rel_path}: {node.name}() calls .{func_name}() (line {sub.lineno})")

                                    # If this function is func_name, find what it calls (callees)
                                    if node.name == func_name:
                                        for sub in ast.walk(node):
                                            if isinstance(sub, ast.Call):
                                                if isinstance(sub.func, ast.Name):
                                                    callees.append(f"calls {sub.func.id}() (line {sub.lineno})")
                                                elif isinstance(sub.func, ast.Attribute):
                                                    callees.append(f"calls .{sub.func.attr}() (line {sub.lineno})")
                        except Exception:
                            continue

            duration_ms = int((time.time() - start_time) * 1000)
            lines = [f"Call graph for '{func_name}' across {files_scanned} Python files:"]
            if callers:
                lines.append("\nCallers (Functions calling " + func_name + "):")
                lines.extend(f"  - {c}" for c in callers[:25])
            else:
                lines.append("\nCallers: None detected.")

            if callees:
                lines.append("\nCallees (Calls inside " + func_name + "):")
                lines.extend(f"  - {c}" for c in callees[:25])
            else:
                lines.append("\nCallees: None detected or definition not found.")

            output = "\n".join(lines)
            output = security.truncate_output(output)
            tokens = self.estimate_tokens(output)
            outcome = ToolOutcome.HIGH_PROGRESS if (callers or callees) else ToolOutcome.LOW_PROGRESS

            return ToolResult(
                tool_name=self.metadata.name,
                success=True,
                output=output,
                outcome=outcome,
                tokens_consumed=tokens,
                execution_time_ms=duration_ms,
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.metadata.name,
                success=False,
                output=f"Error analyzing call graph: {str(e)}",
                outcome=ToolOutcome.FAILURE,
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=str(e)
            )
