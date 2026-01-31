"""Multi-language AST parser using tree-sitter."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tree_sitter_python as tspython
import tree_sitter_typescript as tstypescript
import tree_sitter_javascript as tsjavascript
from tree_sitter import Language, Parser, Node


@dataclass
class Symbol:
    """Represents a code symbol (function, class, etc.)."""
    name: str
    kind: str  # function, class, method, variable, import
    signature: str
    start_line: int
    end_line: int
    docstring: str = ""
    parent: str = ""  # Parent class/module name


@dataclass
class Import:
    """Represents an import statement."""
    module: str
    items: list[str]
    alias: str = ""
    is_relative: bool = False


@dataclass  
class ParsedFile:
    """Result of parsing a file."""
    path: str
    language: str
    symbols: list[Symbol]
    imports: list[Import]
    exports: list[str]


# Initialize parsers
PARSERS: dict[str, Parser] = {}
LANGUAGES: dict[str, Language] = {}


def _init_parsers():
    """Initialize tree-sitter parsers lazily."""
    global PARSERS, LANGUAGES
    
    if PARSERS:
        return
    
    lang_configs = [
        ("python", tspython.language()),
        ("typescript", tstypescript.language_typescript()),
        ("javascript", tsjavascript.language()),
    ]
    
    for name, lang_capsule in lang_configs:
        lang = Language(lang_capsule)
        LANGUAGES[name] = lang
        parser = Parser(lang)
        PARSERS[name] = parser


def get_parser(language: str) -> Parser | None:
    """Get parser for a language."""
    _init_parsers()
    return PARSERS.get(language)


def _get_node_text(node: Node, source: bytes) -> str:
    """Extract text from a node."""
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")


def _extract_docstring(node: Node, source: bytes) -> str:
    """Extract docstring from function/class."""
    for child in node.children:
        if child.type == "expression_statement":
            for sub in child.children:
                if sub.type == "string":
                    doc = _get_node_text(sub, source)
                    return doc.strip("\"'").strip()
        elif child.type == "block":
            return _extract_docstring(child, source)
    return ""


def _extract_python_symbols(tree: Any, source: bytes) -> tuple[list[Symbol], list[Import]]:
    """Extract symbols from Python AST."""
    symbols: list[Symbol] = []
    imports: list[Import] = []
    
    def visit(node: Node, parent_name: str = ""):
        if node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            params_node = node.child_by_field_name("parameters")
            return_node = node.child_by_field_name("return_type")
            
            name = _get_node_text(name_node, source) if name_node else "unknown"
            params = _get_node_text(params_node, source) if params_node else "()"
            returns = f" -> {_get_node_text(return_node, source)}" if return_node else ""
            
            kind = "method" if parent_name else "function"
            signature = f"{params}{returns}"
            
            symbols.append(Symbol(
                name=name,
                kind=kind,
                signature=signature,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                docstring=_extract_docstring(node, source),
                parent=parent_name,
            ))
            
        elif node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            name = _get_node_text(name_node, source) if name_node else "unknown"
            
            # Get base classes
            bases = []
            for child in node.children:
                if child.type == "argument_list":
                    bases.append(_get_node_text(child, source))
            
            signature = bases[0] if bases else ""
            
            symbols.append(Symbol(
                name=name,
                kind="class",
                signature=signature,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                docstring=_extract_docstring(node, source),
                parent=parent_name,
            ))
            
            # Visit class body for methods
            for child in node.children:
                if child.type == "block":
                    for sub in child.children:
                        visit(sub, name)
                        
        elif node.type == "import_statement":
            for child in node.children:
                if child.type == "dotted_name":
                    imports.append(Import(
                        module=_get_node_text(child, source),
                        items=[],
                    ))
                    
        elif node.type == "import_from_statement":
            module = ""
            items = []
            is_relative = False
            
            for child in node.children:
                if child.type == "dotted_name" or child.type == "relative_import":
                    module = _get_node_text(child, source)
                    is_relative = child.type == "relative_import" or module.startswith(".")
                elif child.type == "import_prefix":
                    is_relative = True
                elif child.type in ("identifier", "aliased_import"):
                    items.append(_get_node_text(child, source))
                    
            if module or items:
                imports.append(Import(
                    module=module,
                    items=items,
                    is_relative=is_relative,
                ))
        else:
            for child in node.children:
                visit(child, parent_name)
    
    visit(tree.root_node)
    return symbols, imports


def _extract_typescript_symbols(tree: Any, source: bytes) -> tuple[list[Symbol], list[Import]]:
    """Extract symbols from TypeScript/JavaScript AST."""
    symbols: list[Symbol] = []
    imports: list[Import] = []
    exports: list[str] = []
    
    def visit(node: Node, parent_name: str = ""):
        if node.type in ("function_declaration", "method_definition"):
            name_node = node.child_by_field_name("name")
            params_node = node.child_by_field_name("parameters")
            
            name = _get_node_text(name_node, source) if name_node else "anonymous"
            params = _get_node_text(params_node, source) if params_node else "()"
            
            kind = "method" if parent_name else "function"
            
            symbols.append(Symbol(
                name=name,
                kind=kind,
                signature=params,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                parent=parent_name,
            ))
            
        elif node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            name = _get_node_text(name_node, source) if name_node else "anonymous"
            
            symbols.append(Symbol(
                name=name,
                kind="class",
                signature="",
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                parent=parent_name,
            ))
            
            # Visit class body
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    visit(child, name)
                    
        elif node.type == "arrow_function":
            # Handle arrow functions assigned to variables
            pass
            
        elif node.type == "import_statement":
            source_node = None
            items = []
            
            for child in node.children:
                if child.type == "string":
                    source_node = _get_node_text(child, source).strip("'\"")
                elif child.type == "import_clause":
                    items.append(_get_node_text(child, source))
                    
            if source_node:
                imports.append(Import(
                    module=source_node,
                    items=items,
                ))
        else:
            for child in node.children:
                visit(child, parent_name)
    
    visit(tree.root_node)
    return symbols, imports


def parse_file(file_path: str | Path, language: str | None = None) -> ParsedFile | None:
    """Parse a file and extract symbols."""
    file_path = Path(file_path)
    
    if not file_path.exists():
        return None
    
    # Detect language from extension
    if language is None:
        ext = file_path.suffix.lower()
        lang_map = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".mjs": "javascript",
        }
        language = lang_map.get(ext)
    
    if not language:
        return None
    
    parser = get_parser(language)
    if not parser:
        return None
    
    try:
        with open(file_path, "rb") as f:
            source = f.read()
        
        tree = parser.parse(source)
        
        if language == "python":
            symbols, imports = _extract_python_symbols(tree, source)
        elif language in ("typescript", "javascript"):
            symbols, imports = _extract_typescript_symbols(tree, source)
        else:
            symbols, imports = [], []
        
        # Extract exports (simplified)
        exports = [s.name for s in symbols if not s.name.startswith("_")]
        
        return ParsedFile(
            path=str(file_path),
            language=language,
            symbols=symbols,
            imports=imports,
            exports=exports,
        )
        
    except Exception:
        return None
