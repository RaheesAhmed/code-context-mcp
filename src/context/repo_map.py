"""Repository map generator - condensed codebase overview."""

from pathlib import Path
from collections import defaultdict

from indexer.repository import scan_repository, get_language
from indexer.ast_parser import parse_file, Symbol
from indexer.symbol_extractor import build_symbol_index, SymbolIndex


def generate_repo_map(
    project_path: str | Path,
    max_tokens: int = 8000,
    include_docstrings: bool = False,
) -> str:
    """Generate a condensed repository map showing all symbols.
    
    This is the key feature - fits entire codebase structure in context.
    """
    project_path = Path(project_path).resolve()
    
    if not project_path.exists():
        return f"Error: Project path does not exist: {project_path}"
    
    index = build_symbol_index(project_path)
    
    lines = []
    lines.append(f"# Repository Map: {project_path.name}")
    lines.append("")
    
    files_by_dir: dict[str, list[str]] = defaultdict(list)
    for file_path in sorted(index.symbols_by_file.keys()):
        dir_path = str(Path(file_path).parent)
        files_by_dir[dir_path].append(file_path)
    
    for dir_path in sorted(files_by_dir.keys()):
        if dir_path and dir_path != ".":
            lines.append(f"## {dir_path}/")
        else:
            lines.append("## ./")
        lines.append("")
        
        for file_path in files_by_dir[dir_path]:
            symbols = index.symbols_by_file.get(file_path, [])
            imports = index.imports_by_file.get(file_path, [])
            
            lines.append(f"### {Path(file_path).name}")
            
            if imports:
                import_strs = []
                for imp in imports[:5]:  # Limit imports shown
                    if imp.items:
                        import_strs.append(f"{{{', '.join(imp.items[:3])}}} from {imp.module}")
                    else:
                        import_strs.append(imp.module)
                if import_strs:
                    lines.append(f"  imports: {', '.join(import_strs)}")
            
            classes = [s for s in symbols if s.kind == "class"]
            functions = [s for s in symbols if s.kind == "function"]
            
            for cls in classes:
                sig = f"({cls.signature})" if cls.signature else ""
                lines.append(f"  class {cls.name}{sig}:")
                if include_docstrings and cls.docstring:
                    lines.append(f"    \"\"\"{cls.docstring[:100]}...\"\"\"")
                
                methods = [s for s in symbols if s.kind == "method" and s.parent == cls.name]
                for method in methods:
                    lines.append(f"    def {method.name}{method.signature}")
            
            for func in functions:
                lines.append(f"  def {func.name}{func.signature}")
                if include_docstrings and func.docstring:
                    lines.append(f"    \"\"\"{func.docstring[:80]}...\"\"\"")
            
            lines.append("")
    
    result = "\n".join(lines)
    
    estimated_tokens = len(result) // 4
    if estimated_tokens > max_tokens:
        return _truncate_map(lines, max_tokens)
    
    return result


def _truncate_map(lines: list[str], max_tokens: int) -> str:
    """Truncate map to fit within token limit."""
    result = []
    token_count = 0
    
    for line in lines:
        line_tokens = len(line) // 4 + 1
        if token_count + line_tokens > max_tokens:
            result.append("... (truncated)")
            break
        result.append(line)
        token_count += line_tokens
    
    return "\n".join(result)


def generate_file_context(
    project_path: str | Path,
    target_file: str,
    context_depth: int = 2,
) -> dict:
    """Get a file with smart related context."""
    project_path = Path(project_path).resolve()
    target_path = project_path / target_file
    
    if not target_path.exists():
        return {"error": f"File not found: {target_file}"}
    
    try:
        with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        return {"error": f"Failed to read file: {e}"}
    
    parsed = parse_file(target_path)
    index = build_symbol_index(project_path)
    
    related = []
    seen_files = {target_file}
    
    if target_file in index.files_importing:
        for imp_file in list(index.files_importing[target_file])[:5]:
            if imp_file in seen_files:
                continue
            seen_files.add(imp_file)
            
            imp_path = project_path / imp_file
            if imp_path.exists():
                imp_symbols = index.symbols_by_file.get(imp_file, [])
                related.append({
                    "file": imp_file,
                    "relationship": "imports",
                    "symbols": [f"{s.kind} {s.name}{s.signature}" for s in imp_symbols[:10]],
                })
    
    if target_file in index.files_imported_by:
        for user_file in list(index.files_imported_by[target_file])[:5]:
            if user_file in seen_files:
                continue
            seen_files.add(user_file)
            
            related.append({
                "file": user_file,
                "relationship": "used_by",
            })
    
    return {
        "file": {
            "path": target_file,
            "content": content,
            "language": parsed.language if parsed else "unknown",
            "symbols": [f"{s.kind} {s.name}{s.signature}" for s in (parsed.symbols if parsed else [])],
            "imports": [f"{i.module}" for i in (parsed.imports if parsed else [])],
        },
        "related_files": related,
    }
