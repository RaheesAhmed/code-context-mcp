# Code Context MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

MCP server for codebase understanding. Provides LLM-friendly repository maps, symbol search, and dependency analysis through AST parsing.

## Features

- **Repository Map**: Generate condensed codebase overview with all symbols and signatures
- **Symbol Search**: Find function and class definitions across the codebase
- **Dependency Analysis**: Track imports and file relationships
- **Multi-Language**: Python, TypeScript, JavaScript support via Tree-sitter
- **Gitignore Aware**: Automatically respects `.gitignore` patterns

## Installation

```bash
git clone https://github.com/RaheesAhmed/code-context-mcp.git
cd code-context-mcp
uv sync
```

## Usage

### Development Mode

```bash
uv run mcp dev src/server.py
```

### Claude Desktop Integration

Add to your `claude_desktop_config.json`:

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

## Available Tools

### get_repo_map

Generate a condensed map of the entire codebase showing all classes, functions, and their signatures.

```python
get_repo_map(project_path="/path/to/project")
```

**Output:**
```
# Repository Map: project-name

## src/
### main.py
  def main() -> None
  class Application:
    def run(self) -> None
    def configure(config: dict) -> None
```

### get_file_context

Get file content with related imports and files that use it.

```python
get_file_context(project_path="/path/to/project", file_path="src/main.py")
```

### search_symbols

Find all occurrences of a function, class, or method.

```python
search_symbols(project_path="/path/to/project", symbol_name="parse_file")
```

### get_dependencies

Get import relationships for a specific file.

```python
get_dependencies(project_path="/path/to/project", file_path="src/main.py")
```

### get_project_stats

Get project statistics including file counts and language breakdown.

```python
get_project_stats(project_path="/path/to/project")
```

### read_file

Read file content with optional line range.

```python
read_file(project_path="/path/to/project", file_path="src/main.py", start_line=1, end_line=50)
```

## How It Works

1. **AST Parsing**: Uses Tree-sitter to parse source files into Abstract Syntax Trees
2. **Symbol Extraction**: Extracts functions, classes, methods, and imports from ASTs
3. **Dependency Mapping**: Resolves import statements to build file relationship graphs
4. **Repository Map**: Generates condensed output optimized for LLM context windows

## Project Structure

```
code-context-mcp/
├── src/
│   ├── server.py           # MCP server with tool definitions
│   ├── indexer/
│   │   ├── repository.py   # File scanning with gitignore support
│   │   ├── ast_parser.py   # Tree-sitter AST parsing
│   │   └── symbol_extractor.py
│   └── context/
│       └── repo_map.py     # Repository map generation
├── pyproject.toml
├── LICENSE
└── README.md
```

## Requirements

- Python 3.10+
- [uv](https://github.com/astral-sh/uv)

## License

MIT License - see [LICENSE](LICENSE) for details.

## Author

[Rahees Ahmed](https://github.com/RaheesAhmed)
