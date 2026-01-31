"""Token optimization and change impact analysis."""

import subprocess
from pathlib import Path
from datetime import datetime, timedelta

from indexer.repository import scan_repository
from indexer.ast_parser import parse_file
from indexer.symbol_extractor import build_symbol_index


def get_compressed_context(
    project_path: str | Path,
    files: list[str],
    mode: str = "smart",
) -> str:
    """Get multiple files in token-efficient format.
    
    Args:
        files: List of relative file paths
        mode: 
            - "full": Complete file contents
            - "signatures": Only function/class signatures
            - "smart": Signatures for large files, full for small
    """
    project_path = Path(project_path).resolve()
    
    result_lines = []
    total_chars = 0
    
    for file_path in files:
        full_path = project_path / file_path
        if not full_path.exists():
            result_lines.append(f"### {file_path} (not found)\n")
            continue
        
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            result_lines.append(f"### {file_path} (error: {e})\n")
            continue
        
        file_lines = len(content.split('\n'))
        
        if mode == "full":
            result_lines.append(f"### {file_path}\n```\n{content}\n```\n")
            total_chars += len(content)
        
        elif mode == "signatures":
            result_lines.append(_get_signatures_only(full_path, file_path))
        
        elif mode == "smart":
            if file_lines > 100:
                result_lines.append(_get_signatures_only(full_path, file_path))
            else:
                result_lines.append(f"### {file_path}\n```\n{content}\n```\n")
                total_chars += len(content)
    
    output = '\n'.join(result_lines)
    return {
        "content": output,
        "files_included": len(files),
        "estimated_tokens": len(output) // 4,
        "mode": mode,
    }


def _get_signatures_only(full_path: Path, rel_path: str) -> str:
    """Extract only signatures from a file."""
    parsed = parse_file(full_path)
    if not parsed:
        return f"### {rel_path} (could not parse)\n"
    
    lines = [f"### {rel_path} (signatures only)"]
    
    for symbol in parsed.symbols:
        if symbol.kind == "class":
            lines.append(f"class {symbol.name}:")
        elif symbol.kind in ("function", "method"):
            indent = "    " if symbol.parent else ""
            lines.append(f"{indent}def {symbol.name}{symbol.signature}")
    
    return '\n'.join(lines) + '\n'


def analyze_change_impact(
    project_path: str | Path,
    file_path: str,
) -> dict:
    """Analyze what would be affected by changing a file.
    
    Returns:
    - Direct dependents: Files that import this file
    - Indirect dependents: Files that import direct dependents
    - Symbols exported: What this file provides
    - Risk level: Based on number of dependents
    """
    project_path = Path(project_path).resolve()
    index = build_symbol_index(project_path)
    
    direct_deps = list(index.files_imported_by.get(file_path, set()))
    
    indirect_deps = set()
    for dep in direct_deps:
        for indirect in index.files_imported_by.get(dep, set()):
            if indirect != file_path and indirect not in direct_deps:
                indirect_deps.add(indirect)
    
    symbols = index.symbols_by_file.get(file_path, [])
    exported = [
        f"{s.kind} {s.name}{s.signature}" 
        for s in symbols 
        if not s.name.startswith("_")
    ]
    
    total_affected = len(direct_deps) + len(indirect_deps)
    if total_affected == 0:
        risk = "low"
    elif total_affected <= 5:
        risk = "medium"
    else:
        risk = "high"
    
    return {
        "file": file_path,
        "symbols_exported": exported,
        "direct_dependents": direct_deps,
        "indirect_dependents": list(indirect_deps),
        "total_affected_files": total_affected,
        "risk_level": risk,
        "recommendation": _get_recommendation(risk, total_affected),
    }


def _get_recommendation(risk: str, affected: int) -> str:
    """Generate recommendation based on risk."""
    if risk == "low":
        return "Safe to modify. No other files depend on this."
    elif risk == "medium":
        return f"Moderate caution. {affected} files may be affected. Review before changing public interfaces."
    else:
        return f"High impact. {affected} files depend on this. Consider backward compatibility and thorough testing."


def get_recent_changes(
    project_path: str | Path,
    days: int = 7,
) -> list[dict]:
    """Get recently modified files using git.
    
    Returns list of recently changed files with commit info.
    """
    project_path = Path(project_path).resolve()
    
    try:
        since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        result = subprocess.run(
            ["git", "log", f"--since={since_date}", "--name-only", "--pretty=format:%H|%s|%an|%ad", "--date=short"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode != 0:
            return [{"error": "Git command failed. Is this a git repository?"}]
        
        changes = []
        current_commit = None
        seen_files = set()
        
        for line in result.stdout.split('\n'):
            if not line.strip():
                continue
            
            if '|' in line and line.count('|') >= 3:
                parts = line.split('|')
                current_commit = {
                    "hash": parts[0][:8],
                    "message": parts[1],
                    "author": parts[2],
                    "date": parts[3],
                }
            elif current_commit and line.strip():
                file_path = line.strip()
                if file_path not in seen_files:
                    seen_files.add(file_path)
                    changes.append({
                        "file": file_path,
                        "commit": current_commit["hash"],
                        "message": current_commit["message"][:50],
                        "author": current_commit["author"],
                        "date": current_commit["date"],
                    })
        
        return changes[:50]
        
    except subprocess.TimeoutExpired:
        return [{"error": "Git command timed out"}]
    except FileNotFoundError:
        return [{"error": "Git not found"}]
    except Exception as e:
        return [{"error": str(e)}]


def trace_code_flow(
    project_path: str | Path,
    entry_point: str,
    max_depth: int = 10,
) -> dict:
    """Trace execution flow from an entry point.
    
    Follows function calls to show step-by-step execution path.
    """
    project_path = Path(project_path).resolve()
    index = build_symbol_index(project_path)
    
    symbol_defs = index.symbols_by_name.get(entry_point, [])
    if not symbol_defs:
        return {"error": f"Entry point '{entry_point}' not found"}
    
    file_path, symbol = symbol_defs[0]
    
    visited = set()
    flow = []
    
    def trace(func_name: str, depth: int):
        if depth > max_depth or func_name in visited:
            return
        visited.add(func_name)
        
        defs = index.symbols_by_name.get(func_name, [])
        if not defs:
            flow.append({
                "depth": depth,
                "function": func_name,
                "file": "(external)",
                "type": "external",
            })
            return
        
        f_path, sym = defs[0]
        flow.append({
            "depth": depth,
            "function": func_name,
            "file": f_path,
            "line": sym.start_line,
            "signature": sym.signature,
            "type": "internal",
        })
        
        from analyzer.callgraph import _find_callees
        callees = _find_callees(project_path, f_path, sym, 1)
        for callee in callees[:5]:
            trace(callee["function"], depth + 1)
    
    trace(entry_point, 0)
    
    flow_text = []
    for step in flow:
        indent = "  " * step["depth"]
        if step["type"] == "external":
            flow_text.append(f"{indent}→ {step['function']}() [external]")
        else:
            flow_text.append(f"{indent}→ {step['function']}() @ {step['file']}:{step.get('line', '?')}")
    
    return {
        "entry_point": entry_point,
        "total_steps": len(flow),
        "flow": flow,
        "flow_text": '\n'.join(flow_text),
    }
