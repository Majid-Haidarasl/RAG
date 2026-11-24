"""Static test inventory: test functions per folder, read with ``ast`` (nothing is imported or run).

Parametrized tests count once here; pytest's ``passed`` number counts every
parameter set, so the two numbers differ on purpose.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FolderInventory:
    folder: str
    files: int
    functions: int
    parametrized: int


def count_test_functions(source: str) -> tuple[int, int]:
    """(test functions, of which parametrized) in one module's source."""
    tree = ast.parse(source)
    n = par = 0
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        ) and node.name.startswith("test"):
            n += 1
            for dec in node.decorator_list:
                target = dec.func if isinstance(dec, ast.Call) else dec
                if isinstance(target, ast.Attribute) and target.attr == "parametrize":
                    par += 1
                    break
    return n, par


def inventory(tests_root: Path) -> list[FolderInventory]:
    """One row per folder below ``tests/unit`` (or ``tests_root`` itself when it has no sub-folders)."""
    root = Path(tests_root)
    by: dict[str, list[tuple[int, int]]] = {}
    for path in sorted(root.rglob("test_*.py")):
        rel = path.relative_to(root)
        folder = rel.parts[0] if len(rel.parts) > 1 else "."
        by.setdefault(folder, []).append(
            count_test_functions(path.read_text(encoding="utf-8"))
        )
    return [
        FolderInventory(k, len(v), sum(a for a, _ in v), sum(b for _, b in v))
        for k, v in sorted(by.items())
    ]
