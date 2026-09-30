"""Architecture test ensuring no module-level mutable state or config instances."""

import ast
from pathlib import Path

MUTABLE_DISPLAYS = (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)


def _check_module_assignments(file_path: Path) -> list[str]:
    violations = []
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))

    for stmt in tree.body:
        target_names = []
        val_node = None

        if isinstance(stmt, ast.Assign):
            val_node = stmt.value
            for t in stmt.targets:
                if isinstance(t, ast.Name):
                    target_names.append(t.id)
        elif isinstance(stmt, ast.AnnAssign):
            val_node = stmt.value
            if isinstance(stmt.target, ast.Name):
                target_names.append(stmt.target.id)

        if val_node is None:
            continue

        for name in target_names:
            # 1. Check for Call to a class ending in "Config"
            if isinstance(val_node, ast.Call):
                func = val_node.func
                func_name = ""
                if isinstance(func, ast.Name):
                    func_name = func.id
                elif isinstance(func, ast.Attribute):
                    func_name = func.attr
                if func_name.endswith("Config"):
                    violations.append(
                        f"{file_path.name}:{stmt.lineno}: Assignment to '{name}' instantiates "
                        f"config class '{func_name}' at module level. Pass configs in __init__."
                    )
                elif func_name in {"list", "dict", "set"}:
                    violations.append(
                        f"{file_path.name}:{stmt.lineno}: Assignment to '{name}' calls "
                        f"'{func_name}()' at module level, creating mutable state."
                    )

            # 2. Check for mutable displays/comprehensions (list/dict/set)
            if isinstance(val_node, MUTABLE_DISPLAYS):
                display_type = type(val_node).__name__
                violations.append(
                    f"{file_path.name}:{stmt.lineno}: Assignment to '{name}' uses mutable "
                    f"{display_type} at module level. Use immutable types (tuple, frozenset)."
                )

    return violations


def test_no_global_state() -> None:
    src_skylock = Path(__file__).resolve().parents[2] / "src" / "skylock"
    assert src_skylock.exists(), f"Source directory {src_skylock} not found"

    violations = []
    for py_file in src_skylock.rglob("*.py"):
        violations.extend(_check_module_assignments(py_file))

    assert not violations, "Global state violations found:\n" + "\n".join(violations)
