# Code Context MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

MCP server for deep codebase understanding. Provides LLMs with repository maps, symbol search, call graphs, pattern detection, and token-optimized context.

## Installation

```bash
git clone https://github.com/RaheesAhmed/code-context-mcp.git
cd code-context-mcp
uv sync
```

## Usage

```bash
# Development mode with inspector
uv run mcp dev src/server.py
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "code-context": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/code-context-mcp", "mcp", "run", "src/server.py"]
    }
  }
}
```

## Tools (16 Total)

### Core Tools

| Tool | Description |
|------|-------------|
| `get_repo_map` | Condensed map of all symbols in entire codebase |
| `get_file_context` | File content with related imports |
| `search_symbols` | Find function/class definitions |
| `get_dependencies` | Import relationships for a file |
| `get_project_stats` | File count, lines, language breakdown |
| `read_file` | Read file with optional line range |

### Advanced Search

| Tool | Description |
|------|-------------|
| `find_usages` | Find ALL places where a symbol is used |
| `smart_context` | Auto-find relevant files for a question |
| `semantic_search` | Search code by meaning, not keywords |

### Deep Analysis

| Tool | Description |
|------|-------------|
| `get_call_graph` | Trace callers/callees with Mermaid diagram |
| `get_architecture` | Auto-generate project layer diagram |
| `analyze_patterns` | Detect security, performance, quality issues |

### Optimization

| Tool | Description |
|------|-------------|
| `get_compressed_context` | Token-efficient multi-file context |
| `analyze_change_impact` | What breaks when you change a file |
| `get_recent_changes` | Git history - recently modified files |
| `trace_code_flow` | Step-by-step execution path tracing |

## Examples

```python
# See entire codebase structure
get_repo_map(project_path="/path/to/project")

# Find all usages of a function
find_usages(project_path="/path/to/project", symbol="authenticate")

# Auto-find relevant code for a question
smart_context(project_path="/path/to/project", question="how does auth work?")

# Build call graph with visualization
get_call_graph(project_path="/path/to/project", function_name="main")

# Analyze before making changes
analyze_change_impact(project_path="/path/to/project", file_path="src/core.py")

# Trace execution flow
trace_code_flow(project_path="/path/to/project", entry_point="handleRequest")
```

## Requirements

- Python 3.10+
- [uv](https://github.com/astral-sh/uv)

## License

MIT License - see [LICENSE](LICENSE)

## Author

[Rahees Ahmed](https://github.com/RaheesAhmed)
