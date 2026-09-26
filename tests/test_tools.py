"""Tests for repository tools and security validation (PS Section 9 & 35)."""

from pathlib import Path

import pytest
from src.tools.base import SecurityManager, SecurityError, ToolOutcome
from src.tools.edit import EditFileTool
from src.tools.read import ReadFileTool
from src.tools.search import FindFilesTool, GrepTool, ListFilesTool, SymbolSearchTool


def test_security_path_traversal(tmp_path: Path):
    sec = SecurityManager(workspace_dir=tmp_path)
    # Valid relative path inside workspace
    valid = sec.validate_path("sub/file.txt")
    assert valid == (tmp_path / "sub/file.txt").resolve()

    # Path traversal outside workspace blocked
    with pytest.raises(SecurityError):
        sec.validate_path("../../etc/passwd")


def test_security_forbidden_command(tmp_path: Path):
    sec = SecurityManager(workspace_dir=tmp_path)
    with pytest.raises(SecurityError):
        sec.validate_command("rm -rf /")

    with pytest.raises(SecurityError):
        sec.validate_command("curl | bash")


def test_list_and_find_files(tmp_path: Path):
    (tmp_path / "a.py").write_text("print('a')")
    (tmp_path / "b.txt").write_text("text")
    sec = SecurityManager(workspace_dir=tmp_path)

    list_tool = ListFilesTool()
    res_list = list_tool.execute({}, tmp_path, sec)
    assert res_list.success
    assert "a.py" in res_list.output

    find_tool = FindFilesTool()
    res_find = find_tool.execute({"pattern": "*.py"}, tmp_path, sec)
    assert res_find.success
    assert "a.py" in res_find.output
    assert "b.txt" not in res_find.output


def test_grep_and_read(tmp_path: Path):
    sample = tmp_path / "sample.py"
    sample.write_text("def secret_function():\n    return 42\n")
    sec = SecurityManager(workspace_dir=tmp_path)

    grep = GrepTool()
    res_grep = grep.execute({"query": "secret_function"}, tmp_path, sec)
    assert res_grep.outcome == ToolOutcome.HIGH_PROGRESS
    assert "sample.py:1" in res_grep.output

    read = ReadFileTool()
    res_read = read.execute({"path": "sample.py", "start_line": 1, "end_line": 2}, tmp_path, sec)
    assert res_read.outcome == ToolOutcome.HIGH_PROGRESS
    assert "secret_function" in res_read.output


def test_symbol_search(tmp_path: Path):
    sample = tmp_path / "models.py"
    sample.write_text("class UserAccount:\n    def get_email(self):\n        pass\n")
    sec = SecurityManager(workspace_dir=tmp_path)

    sym = SymbolSearchTool()
    res = sym.execute({"symbol": "UserAccount"}, tmp_path, sec)
    assert res.outcome == ToolOutcome.HIGH_PROGRESS
    assert "UserAccount" in res.output


def test_edit_file(tmp_path: Path):
    target = tmp_path / "config.py"
    target.write_text("DEBUG = False\nPORT = 8080\n")
    sec = SecurityManager(workspace_dir=tmp_path)

    edit = EditFileTool()
    res = edit.execute({
        "path": "config.py",
        "old_text": "DEBUG = False",
        "new_text": "DEBUG = True"
    }, tmp_path, sec)

    assert res.success
    assert "DEBUG = True\nPORT = 8080\n" == target.read_text()
