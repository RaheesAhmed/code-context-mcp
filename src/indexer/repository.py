"""Repository scanner with gitignore support."""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Iterator
import pathspec


@dataclass
class FileInfo:
    """Information about a file in the repository."""
    path: Path
    relative_path: str
    extension: str
    size: int
    language: str


@dataclass
class RepoStats:
    """Repository statistics."""
    total_files: int = 0
    total_lines: int = 0
    languages: dict[str, int] = field(default_factory=dict)
    file_types: dict[str, int] = field(default_factory=dict)


LANGUAGE_MAP = {
    ".py": "python",
    ".pyw": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".txt": "text",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".sql": "sql",
    ".sh": "shell",
    ".bash": "shell",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".xml": "xml",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
}

DEFAULT_IGNORE_PATTERNS = [
    ".git/",
    ".git",
    "__pycache__/",
    "*.pyc",
    "node_modules/",
    ".venv/",
    "venv/",
    ".env",
    "dist/",
    "build/",
    "*.egg-info/",
    ".idea/",
    ".vscode/",
    "*.min.js",
    "*.min.css",
    "*.map",
    ".DS_Store",
    "Thumbs.db",
    "*.log",
    "coverage/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
]


def get_language(extension: str) -> str:
    """Get language name from file extension."""
    return LANGUAGE_MAP.get(extension.lower(), "unknown")


def load_gitignore(project_path: Path) -> pathspec.PathSpec:
    """Load .gitignore patterns from project."""
    patterns = DEFAULT_IGNORE_PATTERNS.copy()
    
    gitignore_path = project_path / ".gitignore"
    if gitignore_path.exists():
        with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
    
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def scan_repository(
    project_path: str | Path,
    max_depth: int = 15,
    include_extensions: list[str] | None = None,
) -> Iterator[FileInfo]:
    """Scan repository and yield file information."""
    project_path = Path(project_path).resolve()
    
    if not project_path.exists():
        raise ValueError(f"Project path does not exist: {project_path}")
    
    ignore_spec = load_gitignore(project_path)
    
    for root, dirs, files in os.walk(project_path):
        root_path = Path(root)
        relative_root = root_path.relative_to(project_path)
        
        current_depth = len(relative_root.parts)
        if current_depth > max_depth:
            dirs.clear()
            continue
        
        # Filter directories in-place
        dirs[:] = [
            d for d in dirs
            if not ignore_spec.match_file(str(relative_root / d) + "/")
            and not d.startswith(".")
        ]
        
        for filename in files:
            file_path = root_path / filename
            relative_path = str(file_path.relative_to(project_path))
            
            if ignore_spec.match_file(relative_path):
                continue
            
            extension = file_path.suffix.lower()
            
            if include_extensions and extension not in include_extensions:
                continue
            
            try:
                size = file_path.stat().st_size
                if size > 1_000_000:  # Skip files > 1MB
                    continue
                    
                yield FileInfo(
                    path=file_path,
                    relative_path=relative_path.replace("\\", "/"),
                    extension=extension,
                    size=size,
                    language=get_language(extension),
                )
            except (OSError, PermissionError):
                continue


def get_repo_stats(project_path: str | Path) -> RepoStats:
    """Get repository statistics."""
    stats = RepoStats()
    
    for file_info in scan_repository(project_path):
        stats.total_files += 1
        
        lang = file_info.language
        stats.languages[lang] = stats.languages.get(lang, 0) + 1
        
        ext = file_info.extension or "no_extension"
        stats.file_types[ext] = stats.file_types.get(ext, 0) + 1
        
        try:
            with open(file_info.path, "r", encoding="utf-8", errors="ignore") as f:
                stats.total_lines += sum(1 for _ in f)
        except (OSError, PermissionError):
            pass
    
    return stats
