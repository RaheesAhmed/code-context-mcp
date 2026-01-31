"""Call graph and architecture analysis."""

from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field
import re

from indexer.repository import scan_repository
from indexer.ast_parser import parse_file
from indexer.symbol_extractor import build_symbol_index, SymbolIndex


def get_call_graph(
    project_path: str | Path,
    function_name: str,
    direction: str = "both",
    depth: int = 3,
) -> dict:
    """Build call graph for a function.
    
    Args:
        function_name: Name of the function to analyze
        direction: "callers" (what calls this), "callees" (what this calls), "both"
        depth: How many levels deep to trace
    """
    project_path = Path(project_path).resolve()
    index = build_symbol_index(project_path)
    
    symbol_defs = index.symbols_by_name.get(function_name, [])
    if not symbol_defs:
        return {"error": f"Symbol '{function_name}' not found"}
    
    file_path, symbol = symbol_defs[0]
    
    result = {
        "function": function_name,
        "file": file_path,
        "line": symbol.start_line,
    }
    
    if direction in ("callers", "both"):
        result["callers"] = _find_callers(project_path, function_name, depth)
    
    if direction in ("callees", "both"):
        result["callees"] = _find_callees(project_path, file_path, symbol, depth)
    
    result["mermaid"] = _generate_mermaid_graph(result, direction)
    
    return result


def _find_callers(project_path: Path, function_name: str, depth: int) -> list:
    """Find all functions that call the target function."""
    callers = []
    pattern = re.compile(r'\b' + re.escape(function_name) + r'\s*\(')
    
    parseable_extensions = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs"}
    
    for file_info in scan_repository(project_path):
        if file_info.extension not in parseable_extensions:
            continue
        
        try:
            full_path = project_path / file_info.relative_path
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            
            if not pattern.search(content):
                continue
            
            parsed = parse_file(full_path)
            if not parsed:
                continue
            
            lines = content.split('\n')
            for symbol in parsed.symbols:
                if symbol.kind in ("function", "method"):
                    func_start = symbol.start_line - 1
                    func_end = symbol.end_line
                    func_body = '\n'.join(lines[func_start:func_end])
                    
                    if pattern.search(func_body) and symbol.name != function_name:
                        callers.append({
                            "file": file_info.relative_path,
                            "function": symbol.name,
                            "line": symbol.start_line,
                        })
        except Exception:
            continue
    
    return callers[:50]


def _find_callees(project_path: Path, file_path: str, symbol, depth: int) -> list:
    """Find all functions called by the target function."""
    callees = []
    
    full_path = project_path / file_path
    if not full_path.exists():
        return callees
    
    try:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        
        func_start = symbol.start_line - 1
        func_end = symbol.end_line
        func_body = ''.join(lines[func_start:func_end])
        
        call_pattern = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(')
        matches = call_pattern.findall(func_body)
        
        keywords = {"if", "for", "while", "with", "try", "except", "return", "print", 
                    "len", "str", "int", "float", "list", "dict", "set", "tuple",
                    "range", "enumerate", "zip", "map", "filter", "sorted", "open"}
        
        seen = set()
        for match in matches:
            if match not in keywords and match not in seen and match != symbol.name:
                seen.add(match)
                callees.append({"function": match})
        
    except Exception:
        pass
    
    return callees[:30]


def _generate_mermaid_graph(result: dict, direction: str) -> str:
    """Generate a Mermaid flowchart diagram."""
    lines = ["graph TD"]
    func_name = result["function"]
    node_id = func_name.replace(".", "_")
    
    lines.append(f'    {node_id}["{func_name}"]')
    
    if "callers" in result:
        for i, caller in enumerate(result["callers"][:10]):
            caller_id = f"caller_{i}"
            caller_name = caller["function"]
            lines.append(f'    {caller_id}["{caller_name}"] --> {node_id}')
    
    if "callees" in result:
        for i, callee in enumerate(result["callees"][:10]):
            callee_id = f"callee_{i}"
            callee_name = callee["function"]
            lines.append(f'    {node_id} --> {callee_id}["{callee_name}"]')
    
    return '\n'.join(lines)


def get_architecture(
    project_path: str | Path,
    format: str = "mermaid",
) -> str:
    """Generate architecture diagram showing project layers.
    
    Auto-detects:
    - API routes / endpoints
    - Business logic / services
    - Data layer / models
    - UI components
    - Utilities
    """
    project_path = Path(project_path).resolve()
    
    layers = {
        "api": [],
        "services": [],
        "models": [],
        "components": [],
        "utils": [],
        "config": [],
    }
    
    for file_info in scan_repository(project_path):
        path = file_info.relative_path.lower().replace("\\", "/")
        
        if any(x in path for x in ["api/", "routes/", "endpoints/", "handlers/"]):
            layers["api"].append(file_info.relative_path)
        elif any(x in path for x in ["service", "business", "logic", "core/"]):
            layers["services"].append(file_info.relative_path)
        elif any(x in path for x in ["model", "schema", "entity", "database", "db/"]):
            layers["models"].append(file_info.relative_path)
        elif any(x in path for x in ["component", "ui/", "views/", "pages/"]):
            layers["components"].append(file_info.relative_path)
        elif any(x in path for x in ["util", "helper", "lib/", "common/"]):
            layers["utils"].append(file_info.relative_path)
        elif any(x in path for x in ["config", "setting", "env"]):
            layers["config"].append(file_info.relative_path)
    
    if format == "mermaid":
        return _generate_architecture_mermaid(layers, project_path.name)
    else:
        return _generate_architecture_ascii(layers, project_path.name)


def _generate_architecture_mermaid(layers: dict, project_name: str) -> str:
    """Generate Mermaid architecture diagram."""
    lines = [
        "graph TB",
        f'    subgraph {project_name}',
    ]
    
    if layers["components"]:
        lines.append('        subgraph UI["UI Layer"]')
        for i, f in enumerate(layers["components"][:5]):
            lines.append(f'            comp{i}["{Path(f).name}"]')
        lines.append('        end')
    
    if layers["api"]:
        lines.append('        subgraph API["API Layer"]')
        for i, f in enumerate(layers["api"][:5]):
            lines.append(f'            api{i}["{Path(f).name}"]')
        lines.append('        end')
    
    if layers["services"]:
        lines.append('        subgraph Services["Business Logic"]')
        for i, f in enumerate(layers["services"][:5]):
            lines.append(f'            svc{i}["{Path(f).name}"]')
        lines.append('        end')
    
    if layers["models"]:
        lines.append('        subgraph Data["Data Layer"]')
        for i, f in enumerate(layers["models"][:5]):
            lines.append(f'            model{i}["{Path(f).name}"]')
        lines.append('        end')
    
    lines.append('    end')
    
    if layers["components"] and layers["api"]:
        lines.append('    UI --> API')
    if layers["api"] and layers["services"]:
        lines.append('    API --> Services')
    if layers["services"] and layers["models"]:
        lines.append('    Services --> Data')
    elif layers["api"] and layers["models"]:
        lines.append('    API --> Data')
    
    return '\n'.join(lines)


def _generate_architecture_ascii(layers: dict, project_name: str) -> str:
    """Generate ASCII architecture diagram."""
    lines = [
        f"=== {project_name} Architecture ===",
        "",
    ]
    
    layer_names = [
        ("components", "UI Layer"),
        ("api", "API Layer"),
        ("services", "Business Logic"),
        ("models", "Data Layer"),
        ("utils", "Utilities"),
        ("config", "Configuration"),
    ]
    
    for key, name in layer_names:
        if layers[key]:
            lines.append(f"┌─ {name} ({len(layers[key])} files)")
            for f in layers[key][:5]:
                lines.append(f"│  └─ {Path(f).name}")
            if len(layers[key]) > 5:
                lines.append(f"│  └─ ... and {len(layers[key]) - 5} more")
            lines.append("│")
    
    return '\n'.join(lines)
