"""Pattern detection - find design patterns, anti-patterns, and issues."""

import re
from pathlib import Path
from dataclasses import dataclass

from indexer.repository import scan_repository
from indexer.ast_parser import parse_file


@dataclass
class Issue:
    """Detected issue in code."""
    file: str
    line: int
    category: str
    severity: str
    message: str
    code: str = ""


def analyze_patterns(
    project_path: str | Path,
    checks: list[str] | None = None,
) -> dict:
    """Analyze codebase for patterns and issues.
    
    Args:
        checks: List of check categories. Options:
            - "security": SQL injection, hardcoded secrets, etc.
            - "performance": N+1 queries, blocking I/O, etc.
            - "quality": God objects, code duplication, etc.
            - "all": Run all checks (default)
    """
    project_path = Path(project_path).resolve()
    
    if not checks or "all" in checks:
        checks = ["security", "performance", "quality"]
    
    issues: list[Issue] = []
    patterns_found = {
        "design_patterns": [],
        "frameworks": [],
    }
    
    parseable_extensions = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs"}
    
    for file_info in scan_repository(project_path):
        if file_info.extension not in parseable_extensions:
            continue
        
        full_path = project_path / file_info.relative_path
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                lines = content.split('\n')
        except Exception:
            continue
        
        rel_path = file_info.relative_path
        
        if "security" in checks:
            issues.extend(_check_security(rel_path, content, lines))
        
        if "performance" in checks:
            issues.extend(_check_performance(rel_path, content, lines))
        
        if "quality" in checks:
            issues.extend(_check_quality(rel_path, content, lines, full_path))
        
        _detect_patterns(rel_path, content, patterns_found)
    
    return {
        "summary": {
            "total_issues": len(issues),
            "critical": sum(1 for i in issues if i.severity == "critical"),
            "warning": sum(1 for i in issues if i.severity == "warning"),
            "info": sum(1 for i in issues if i.severity == "info"),
        },
        "issues": [
            {
                "file": i.file,
                "line": i.line,
                "category": i.category,
                "severity": i.severity,
                "message": i.message,
                "code": i.code,
            }
            for i in issues[:50]
        ],
        "patterns_detected": patterns_found,
    }


def _check_security(file_path: str, content: str, lines: list[str]) -> list[Issue]:
    """Check for security issues."""
    issues = []
    
    secret_patterns = [
        (r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']+["\']', "Hardcoded password"),
        (r'(?i)(api_key|apikey|api-key)\s*=\s*["\'][^"\']+["\']', "Hardcoded API key"),
        (r'(?i)(secret|token)\s*=\s*["\'][a-zA-Z0-9]{20,}["\']', "Hardcoded secret/token"),
        (r'(?i)(aws_access_key|aws_secret)', "AWS credentials in code"),
    ]
    
    for i, line in enumerate(lines, 1):
        for pattern, message in secret_patterns:
            if re.search(pattern, line):
                if not any(x in line.lower() for x in ["example", "placeholder", "xxx", "your_", "env.", "process.env", "os.environ"]):
                    issues.append(Issue(
                        file=file_path,
                        line=i,
                        category="security",
                        severity="critical",
                        message=message,
                        code=line.strip()[:80],
                    ))
    
    sql_pattern = r'(execute|query|raw)\s*\([^)]*["\'][^"\']*\s*\+|f["\'].*\{.*\}.*(?:SELECT|INSERT|UPDATE|DELETE)'
    for i, line in enumerate(lines, 1):
        if re.search(sql_pattern, line, re.IGNORECASE):
            issues.append(Issue(
                file=file_path,
                line=i,
                category="security",
                severity="warning",
                message="Potential SQL injection - use parameterized queries",
                code=line.strip()[:80],
            ))
    
    return issues


def _check_performance(file_path: str, content: str, lines: list[str]) -> list[Issue]:
    """Check for performance issues."""
    issues = []
    
    for i, line in enumerate(lines, 1):
        if re.search(r'time\.sleep\s*\(\s*\d', line):
            issues.append(Issue(
                file=file_path,
                line=i,
                category="performance",
                severity="info",
                message="Blocking sleep - consider async alternative",
                code=line.strip()[:80],
            ))
        
        if re.search(r'for\s+.*\s+in\s+.*:\s*$', line):
            next_lines = '\n'.join(lines[i:i+3])
            if re.search(r'\.(find|get|query|fetch|select)', next_lines, re.IGNORECASE):
                issues.append(Issue(
                    file=file_path,
                    line=i,
                    category="performance",
                    severity="warning",
                    message="Potential N+1 query - consider batch fetching",
                    code=line.strip()[:80],
                ))
    
    return issues


def _check_quality(file_path: str, content: str, lines: list[str], full_path: Path) -> list[Issue]:
    """Check for code quality issues."""
    issues = []
    
    parsed = parse_file(full_path)
    if parsed:
        for symbol in parsed.symbols:
            if symbol.kind in ("function", "method"):
                func_lines = symbol.end_line - symbol.start_line + 1
                if func_lines > 100:
                    issues.append(Issue(
                        file=file_path,
                        line=symbol.start_line,
                        category="quality",
                        severity="warning",
                        message=f"Function too long ({func_lines} lines) - consider splitting",
                        code=f"{symbol.name}{symbol.signature}",
                    ))
            
            if symbol.kind == "class":
                methods = [s for s in parsed.symbols if s.parent == symbol.name]
                if len(methods) > 20:
                    issues.append(Issue(
                        file=file_path,
                        line=symbol.start_line,
                        category="quality",
                        severity="warning",
                        message=f"Class has too many methods ({len(methods)}) - possible God object",
                        code=f"class {symbol.name}",
                    ))
    
    if len(lines) > 500:
        issues.append(Issue(
            file=file_path,
            line=1,
            category="quality",
            severity="info",
            message=f"Large file ({len(lines)} lines) - consider splitting",
        ))
    
    return issues


def _detect_patterns(file_path: str, content: str, patterns_found: dict):
    """Detect design patterns and frameworks."""
    
    if re.search(r'_instance\s*=\s*None|__new__\s*\(|getInstance\s*\(', content):
        if "Singleton" not in patterns_found["design_patterns"]:
            patterns_found["design_patterns"].append("Singleton")
    
    if re.search(r'def\s+create.*\(.*type|Factory\s*\(', content):
        if "Factory" not in patterns_found["design_patterns"]:
            patterns_found["design_patterns"].append("Factory")
    
    if re.search(r'@observe|subscribe\s*\(|addEventListener', content):
        if "Observer" not in patterns_found["design_patterns"]:
            patterns_found["design_patterns"].append("Observer")
    
    if "react" in content.lower() or "useState" in content or "useEffect" in content:
        if "React" not in patterns_found["frameworks"]:
            patterns_found["frameworks"].append("React")
    
    if "fastapi" in content.lower() or "@app.get" in content or "@router" in content:
        if "FastAPI" not in patterns_found["frameworks"]:
            patterns_found["frameworks"].append("FastAPI")
    
    if "express" in content.lower() or "app.get(" in content or "router.get(" in content:
        if "Express" not in patterns_found["frameworks"]:
            patterns_found["frameworks"].append("Express")
    
    if "nextjs" in content.lower() or "next/router" in content or "'use client'" in content:
        if "Next.js" not in patterns_found["frameworks"]:
            patterns_found["frameworks"].append("Next.js")
