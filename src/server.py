"""Code Context MCP Server - Deep codebase understanding for LLMs."""

import sys
from pathlib import Path

# Add src directory to path for imports when run directly
_src_dir = Path(__file__).parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))
if str(_src_dir.parent) not in sys.path:
    sys.path.insert(0, str(_src_dir.parent))

from typing import Annotated
from mcp.server.fastmcp import FastMCP

from indexer.repository import scan_repository, get_repo_stats
from indexer.ast_parser import parse_file
from indexer.symbol_extractor import build_symbol_index, find_symbol, get_file_dependencies
from context.repo_map import generate_repo_map, generate_file_context


mcp = FastMCP(
    "Code Context",
    instructions="""Code Context server provides deep codebase understanding.
    
Use these tools:
- get_repo_map: Get condensed view of entire codebase (start here!)
- get_file_context: Get file with related imports and usages
- search_symbols: Find function/class definitions
- get_dependencies: See what a file imports and what imports it
- get_project_stats: Get project statistics
"""
)


@mcp.tool()
def get_repo_map(
    project_path: Annotated[str, "Absolute path to the project root"],
    max_tokens: Annotated[int, "Maximum tokens for the map"] = 8000,
    include_docstrings: Annotated[bool, "Include docstrings in output"] = False,
) -> str:
    """Get a condensed repository map showing all symbols.
    
    This is the most important tool - it gives you complete codebase 
    structure in a single context window. Start with this to understand
    any codebase.
    
    Returns: Markdown-formatted map with all classes, functions, and their signatures.
    """
    try:
        return generate_repo_map(project_path, max_tokens, include_docstrings)
    except Exception as e:
        return f"Error generating repo map: {e}"


@mcp.tool()
def get_file_context(
    project_path: Annotated[str, "Absolute path to the project root"],
    file_path: Annotated[str, "Relative path to the file within the project"],
    context_depth: Annotated[int, "How deep to traverse dependencies"] = 2,
) -> dict:
    """Get a file with smart related context.
    
    Returns the file content along with:
    - Symbols defined in the file
    - Files it imports (with their symbols)
    - Files that import this file
    
    Use this after get_repo_map to dive into specific files.
    """
    try:
        return generate_file_context(project_path, file_path, context_depth)
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def search_symbols(
    project_path: Annotated[str, "Absolute path to the project root"],
    symbol_name: Annotated[str, "Name of the symbol to search for"],
) -> list[dict]:
    """Find all occurrences of a symbol (function, class, method).
    
    Returns list of matches with file path, line numbers, and signature.
    """
    try:
        index = build_symbol_index(project_path)
        results = find_symbol(index, symbol_name)
        
        return [
            {
                "file": file_path,
                "kind": symbol.kind,
                "name": symbol.name,
                "signature": symbol.signature,
                "line": symbol.start_line,
                "end_line": symbol.end_line,
                "parent": symbol.parent,
                "docstring": symbol.docstring[:200] if symbol.docstring else "",
            }
            for file_path, symbol in results
        ]
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool()
def get_dependencies(
    project_path: Annotated[str, "Absolute path to the project root"],
    file_path: Annotated[str, "Relative path to the file"],
) -> dict:
    """Get dependency information for a file.
    
    Returns:
    - imports: Files this file imports
    - imported_by: Files that import this file
    - symbols: Symbols defined in this file
    """
    try:
        index = build_symbol_index(project_path)
        deps = get_file_dependencies(index, file_path)
        
        return {
            "file": file_path,
            "imports": deps["imports"],
            "imported_by": deps["imported_by"],
            "symbols": [
                f"{s.kind} {s.name}{s.signature}"
                for s in deps["symbols"]
            ],
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def get_project_stats(
    project_path: Annotated[str, "Absolute path to the project root"],
) -> dict:
    """Get project statistics.
    
    Returns: Total files, lines, languages breakdown.
    """
    try:
        stats = get_repo_stats(project_path)
        return {
            "project": Path(project_path).name,
            "total_files": stats.total_files,
            "total_lines": stats.total_lines,
            "languages": dict(sorted(
                stats.languages.items(),
                key=lambda x: x[1],
                reverse=True
            )),
            "file_types": dict(sorted(
                stats.file_types.items(),
                key=lambda x: x[1],
                reverse=True
            )),
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def read_file(
    project_path: Annotated[str, "Absolute path to the project root"],
    file_path: Annotated[str, "Relative path to the file"],
    start_line: Annotated[int, "Start line (1-indexed)"] = 1,
    end_line: Annotated[int, "End line (inclusive), -1 for entire file"] = -1,
) -> dict:
    """Read file content with optional line range.
    
    Use this to read specific sections after using get_repo_map
    to identify what you need.
    """
    try:
        full_path = Path(project_path) / file_path
        
        if not full_path.exists():
            return {"error": f"File not found: {file_path}"}
        
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        
        if end_line == -1:
            end_line = total_lines
        
        start_idx = max(0, start_line - 1)
        end_idx = min(total_lines, end_line)
        
        content = "".join(lines[start_idx:end_idx])
        
        return {
            "file": file_path,
            "total_lines": total_lines,
            "showing_lines": f"{start_line}-{end_line}",
            "content": content,
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.resource("project://{project_path}/map")
def project_map_resource(project_path: str) -> str:
    """Get repository map as a resource."""
    return generate_repo_map(project_path)


@mcp.prompt(title="Understand Codebase")
def understand_codebase_prompt(project_path: str) -> str:
    """Prompt template for understanding a new codebase."""
    return f"""I need to understand the codebase at: {project_path}

Please follow these steps:
1. First, use get_repo_map to see the complete project structure
2. Identify the main entry points and key files
3. Analyze the architecture and how components connect
4. Explain what this project does and how it's organized

Provide a comprehensive overview including:
- What the project does
- Main technologies used
- Key files and their purposes
- How to navigate the codebase
"""


@mcp.prompt(title="Find and Fix Issues")
def find_issues_prompt(project_path: str, issue_description: str = "") -> str:
    """Prompt template for finding issues in code."""
    return f"""Analyze the codebase at: {project_path}

Issue to investigate: {issue_description or "General code quality review"}

Steps:
1. Use get_repo_map to understand the structure
2. Use search_symbols to find relevant code
3. Use get_file_context to examine specific files
4. Use get_dependencies to understand relationships

Look for:
- Potential bugs or logic errors
- Performance issues
- Missing error handling
- Code that doesn't match patterns in the codebase
"""


def main():
    """Run the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
