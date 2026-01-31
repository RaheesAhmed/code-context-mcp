"""Symbol extraction and call graph building."""

from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict

from indexer.repository import scan_repository, FileInfo
from indexer.ast_parser import parse_file, ParsedFile, Symbol, Import


@dataclass
class SymbolIndex:
    """Index of all symbols in a repository."""
    symbols_by_file: dict[str, list[Symbol]] = field(default_factory=dict)
    symbols_by_name: dict[str, list[tuple[str, Symbol]]] = field(default_factory=dict)
    imports_by_file: dict[str, list[Import]] = field(default_factory=dict)
    files_importing: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    files_imported_by: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))


def build_symbol_index(project_path: str | Path) -> SymbolIndex:
    """Build a complete symbol index for a project."""
    project_path = Path(project_path).resolve()
    index = SymbolIndex()
    
    parseable_extensions = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs"}
    
    for file_info in scan_repository(project_path, include_extensions=list(parseable_extensions)):
        parsed = parse_file(file_info.path)
        if not parsed:
            continue
        
        rel_path = file_info.relative_path
        index.symbols_by_file[rel_path] = parsed.symbols
        index.imports_by_file[rel_path] = parsed.imports
        
        for symbol in parsed.symbols:
            if symbol.name not in index.symbols_by_name:
                index.symbols_by_name[symbol.name] = []
            index.symbols_by_name[symbol.name].append((rel_path, symbol))
        
        for imp in parsed.imports:
            module_path = _resolve_import(project_path, rel_path, imp)
            if module_path:
                index.files_importing[rel_path].add(module_path)
                index.files_imported_by[module_path].add(rel_path)
    
    return index


def _resolve_import(project_path: Path, current_file: str, imp: Import) -> str | None:
    """Resolve an import to a file path."""
    if not imp.module:
        return None
    
    if imp.is_relative:
        current_dir = Path(current_file).parent
        module_parts = imp.module.lstrip(".").split(".")
        dots = len(imp.module) - len(imp.module.lstrip("."))
        
        target_dir = current_dir
        for _ in range(dots - 1):
            target_dir = target_dir.parent
        
        for part in module_parts:
            target_dir = target_dir / part
        
        for ext in [".py", ".ts", ".tsx", ".js", ".jsx"]:
            candidate = str(target_dir) + ext
            if (project_path / candidate).exists():
                return candidate.replace("\\", "/")
            
            init_candidate = str(target_dir / "__init__.py")
            if (project_path / init_candidate).exists():
                return init_candidate.replace("\\", "/")
        
        return str(target_dir).replace("\\", "/") + ".py"
    
    return None


def find_symbol(index: SymbolIndex, name: str) -> list[tuple[str, Symbol]]:
    """Find all occurrences of a symbol by name."""
    return index.symbols_by_name.get(name, [])


def get_file_dependencies(index: SymbolIndex, file_path: str) -> dict:
    """Get import and usage information for a file."""
    return {
        "imports": list(index.files_importing.get(file_path, set())),
        "imported_by": list(index.files_imported_by.get(file_path, set())),
        "symbols": index.symbols_by_file.get(file_path, []),
    }
