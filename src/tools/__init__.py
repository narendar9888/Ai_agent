"""Tools module registry for ACTP."""

from typing import Dict
from .base import BaseTool, ToolCategory, ToolMetadata, ToolOutcome, ToolResult, SecurityManager, SecurityError
from .search import ListFilesTool, FindFilesTool, GrepTool, SymbolSearchTool
from .read import ReadFileTool
from .edit import EditFileTool, ApplyPatchTool
from .git import GitStatusTool, GitDiffTool
from .shell import RunCommandTool
from .tests import RunTestsTool, RunBuildTool, DependencySearchTool, CallGraphTool


def get_default_tools() -> Dict[str, BaseTool]:
    """Returns a dictionary of all available tools keyed by tool name."""
    tools: list[BaseTool] = [
        ListFilesTool(),
        FindFilesTool(),
        GrepTool(),
        SymbolSearchTool(),
        ReadFileTool(),
        DependencySearchTool(),
        CallGraphTool(),
        GitStatusTool(),
        GitDiffTool(),
        EditFileTool(),
        ApplyPatchTool(),
        RunCommandTool(),
        RunTestsTool(),
        RunBuildTool(),
    ]
    return {tool.metadata.name: tool for tool in tools}


__all__ = [
    "BaseTool",
    "ToolCategory",
    "ToolMetadata",
    "ToolOutcome",
    "ToolResult",
    "SecurityManager",
    "SecurityError",
    "ListFilesTool",
    "FindFilesTool",
    "GrepTool",
    "SymbolSearchTool",
    "ReadFileTool",
    "EditFileTool",
    "ApplyPatchTool",
    "GitStatusTool",
    "GitDiffTool",
    "RunCommandTool",
    "RunTestsTool",
    "RunBuildTool",
    "DependencySearchTool",
    "CallGraphTool",
    "get_default_tools",
]
