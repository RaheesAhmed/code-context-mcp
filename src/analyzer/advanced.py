"""Advanced analysis tools for v2.0 features."""

import re
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field

from indexer.repository import scan_repository
from indexer.ast_parser import parse_file
from indexer.symbol_extractor import build_symbol_index, SymbolIndex


def find_all_usages(project_path: str | Path, symbol_name: str) -> list[dict]:
    """Find all places where a symbol is used (not just defined).
    
    Searches through all files for references to the symbol.
    """
    project_path = Path(project_path).resolve()
    usages = []
    
    pattern = re.compile(r'\b' + re.escape(symbol_name) + r'\b')
    
    parseable_extensions = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs"}
    
    for file_info in scan_repository(project_path):
        if file_info.extension not in parseable_extensions:
            continue
            
        try:
            full_path = project_path / file_info.relative_path
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                if pattern.search(line):
                    usages.append({
                        "file": file_info.relative_path,
                        "line": line_num,
                        "content": line.strip()[:150],
                        "type": _classify_usage(line, symbol_name),
                    })
        except Exception:
            continue
    
    return usages


def _classify_usage(line: str, symbol_name: str) -> str:
    """Classify the type of usage."""
    line = line.strip()
    
    if line.startswith(("def ", "async def ")) and f"{symbol_name}(" in line:
        return "definition"
    if line.startswith("class ") and symbol_name in line:
        return "definition"
    if "import" in line and symbol_name in line:
        return "import"
    if f"{symbol_name}(" in line:
        return "call"
    if f".{symbol_name}" in line:
        return "attribute"
    if f"{symbol_name} =" in line or f"{symbol_name}:" in line:
        return "assignment"
    return "reference"


def get_smart_context(
    project_path: str | Path,
    question: str,
    max_tokens: int = 15000,
) -> dict:
    """Auto-find all relevant files for a question.
    
    Analyzes the question to find related code sections.
    """
    project_path = Path(project_path).resolve()
    index = build_symbol_index(project_path)
    
    keywords = _extract_keywords(question)
    
    file_scores: dict[str, float] = defaultdict(float)
    matched_symbols: dict[str, list[str]] = defaultdict(list)
    
    for keyword in keywords:
        keyword_lower = keyword.lower()
        
        for symbol_name, occurrences in index.symbols_by_name.items():
            if keyword_lower in symbol_name.lower():
                for file_path, symbol in occurrences:
                    score = 10 if keyword_lower == symbol_name.lower() else 5
                    file_scores[file_path] += score
                    matched_symbols[file_path].append(
                        f"{symbol.kind} {symbol.name}{symbol.signature}"
                    )
    
    for keyword in keywords:
        usages = find_all_usages(project_path, keyword)
        for usage in usages:
            file_scores[usage["file"]] += 1
    
    sorted_files = sorted(file_scores.items(), key=lambda x: x[1], reverse=True)
    
    result_files = []
    total_chars = 0
    max_chars = max_tokens * 4
    
    for file_path, score in sorted_files[:20]:
        full_path = project_path / file_path
        if not full_path.exists():
            continue
            
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            
            if total_chars + len(content) > max_chars:
                if len(result_files) < 3:
                    content = content[:max_chars - total_chars]
                else:
                    continue
            
            total_chars += len(content)
            result_files.append({
                "file": file_path,
                "relevance_score": score,
                "matched_symbols": list(set(matched_symbols.get(file_path, []))),
                "content": content,
            })
            
            if total_chars >= max_chars:
                break
                
        except Exception:
            continue
    
    return {
        "question": question,
        "keywords_detected": keywords,
        "files_analyzed": len(file_scores),
        "relevant_files": result_files,
        "total_tokens_estimate": total_chars // 4,
    }


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from a question."""
    stop_words = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "must", "shall", "can", "need", "dare",
        "i", "you", "he", "she", "it", "we", "they", "what", "which", "who",
        "when", "where", "why", "how", "all", "each", "every", "both", "few",
        "more", "most", "other", "some", "such", "no", "nor", "not", "only",
        "own", "same", "so", "than", "too", "very", "just", "and", "but",
        "if", "or", "because", "as", "until", "while", "of", "at", "by",
        "for", "with", "about", "against", "between", "into", "through",
        "during", "before", "after", "above", "below", "to", "from", "up",
        "down", "in", "out", "on", "off", "over", "under", "again", "further",
        "then", "once", "here", "there", "this", "that", "these", "those",
        "work", "works", "working", "code", "file", "files", "function",
        "find", "show", "get", "make", "explain", "understand",
    }
    
    words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', text)
    
    keywords = []
    for word in words:
        if word.lower() not in stop_words and len(word) > 2:
            keywords.append(word)
    
    return list(dict.fromkeys(keywords))


def semantic_search(
    project_path: str | Path,
    query: str,
    top_k: int = 10,
) -> list[dict]:
    """Search code by meaning using keyword matching and symbol analysis.
    
    For true semantic search, would need embeddings. This version uses
    smart keyword matching as a foundation.
    """
    project_path = Path(project_path).resolve()
    
    keywords = _extract_keywords(query)
    
    results = []
    seen_files = set()
    
    index = build_symbol_index(project_path)
    for keyword in keywords:
        keyword_lower = keyword.lower()
        for symbol_name, occurrences in index.symbols_by_name.items():
            if keyword_lower in symbol_name.lower():
                for file_path, symbol in occurrences:
                    if file_path not in seen_files:
                        seen_files.add(file_path)
                        results.append({
                            "file": file_path,
                            "match_type": "symbol",
                            "symbol": f"{symbol.kind} {symbol.name}{symbol.signature}",
                            "line": symbol.start_line,
                            "relevance": "high" if keyword_lower == symbol_name.lower() else "medium",
                        })
    
    for keyword in keywords:
        usages = find_all_usages(project_path, keyword)
        for usage in usages[:5]:
            result_key = f"{usage['file']}:{usage['line']}"
            if result_key not in seen_files:
                seen_files.add(result_key)
                results.append({
                    "file": usage["file"],
                    "match_type": "content",
                    "content": usage["content"],
                    "line": usage["line"],
                    "usage_type": usage["type"],
                    "relevance": "medium",
                })
    
    results.sort(key=lambda x: (
        0 if x.get("relevance") == "high" else 1,
        0 if x.get("match_type") == "symbol" else 1,
    ))
    
    return results[:top_k]
