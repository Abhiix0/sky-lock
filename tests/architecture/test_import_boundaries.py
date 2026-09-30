"""Architecture test enforcing package import boundaries."""

import ast
from pathlib import Path

# Package -> allowed skylock subpackages it may import (self is always allowed)
ALLOWED_SKYLOK_IMPORTS = {
    "config": set(),  # stdlib only
    "core": {"config"},
    "vision": {"core", "config"},
    "tracking": {"core", "config"},
    "control": {"core", "config"},
    "simulation": {"core", "config"},
    "input": {"core", "config"},
    "metrics": {"core", "config"},
    "benchmark": {"app", "metrics", "config", "core"},
    "app": {
        "config",
        "core",
        "vision",
        "tracking",
        "control",
        "simulation",
        "input",
        "metrics",
        "benchmark",
    },
    "ui": {"app", "config", "core", "benchmark"},
}

FORBIDDEN_SKYLOK_IMPORTS = {
    "core": {
        "vision",
        "tracking",
        "control",
        "simulation",
        "input",
        "metrics",
        "benchmark",
        "app",
        "ui",
    },
    "config": {
        "core",
        "vision",
        "tracking",
        "control",
        "simulation",
        "input",
        "metrics",
        "benchmark",
        "app",
        "ui",
    },
    "vision": {"simulation", "metrics", "tracking", "control", "ui"},
    "tracking": {"simulation", "metrics", "input", "ui"},
    "control": {"simulation", "metrics", "ui"},
    "simulation": {"tracking", "vision", "control", "metrics", "ui"},
    "input": {"simulation", "tracking", "ui"},
    "metrics": {"ui"},
    "benchmark": {"ui"},
    "app": {"ui"},  # At module level; app.main may lazily import ui inside function
    "ui": {"simulation", "tracking", "vision", "control", "input", "metrics"},
}


def _get_imported_skylock_submodules(node: ast.AST) -> list[tuple[str, bool]]:
    """Return list of (subpackage_name, is_module_level)."""
    results = []

    def get_skylock_subpkg(target: str) -> str | None:
        parts = target.split(".")
        if parts[0] == "skylock" and len(parts) > 1:
            return parts[1]
        return None

    class ImportVisitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.scope_stack = ["module"]

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.scope_stack.append("function")
            self.generic_visit(node)
            self.scope_stack.pop()

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.scope_stack.append("function")
            self.generic_visit(node)
            self.scope_stack.pop()

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.scope_stack.append("class")
            self.generic_visit(node)
            self.scope_stack.pop()

        def visit_Import(self, node: ast.Import) -> None:
            is_module_level = len(self.scope_stack) == 1 and self.scope_stack[0] == "module"
            for alias in node.names:
                sub = get_skylock_subpkg(alias.name)
                if sub:
                    results.append((sub, is_module_level))

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            is_module_level = len(self.scope_stack) == 1 and self.scope_stack[0] == "module"
            if node.module:
                if node.module == "skylock":
                    for alias in node.names:
                        results.append((alias.name.split(".")[0], is_module_level))
                else:
                    sub = get_skylock_subpkg(node.module)
                    if sub:
                        results.append((sub, is_module_level))

    ImportVisitor().visit(node)
    return results


def test_import_boundaries() -> None:
    src_skylock = Path(__file__).resolve().parents[2] / "src" / "skylock"
    assert src_skylock.exists(), f"Source directory {src_skylock} not found"

    violations = []

    for pkg_dir in src_skylock.iterdir():
        if not pkg_dir.is_dir() or pkg_dir.name.startswith((".", "_")):
            continue
        pkg_name = pkg_dir.name
        if pkg_name not in ALLOWED_SKYLOK_IMPORTS:
            continue

        allowed = ALLOWED_SKYLOK_IMPORTS[pkg_name] | {pkg_name}

        for py_file in pkg_dir.rglob("*.py"):
            file_allowed = allowed
            if pkg_name == "core" and py_file.name == "pipeline.py":
                file_allowed = allowed | {"vision", "tracking", "control"}

            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except SyntaxError as e:
                violations.append(f"Syntax error in {py_file}: {e}")
                continue

            imports = _get_imported_skylock_submodules(tree)
            for imported_sub, is_mod_level in imports:
                is_lazy_app_main_ui = (
                    pkg_name == "app"
                    and py_file.name == "main.py"
                    and imported_sub == "ui"
                    and not is_mod_level
                )

                # Check general allowed imports
                if imported_sub not in file_allowed:
                    if is_lazy_app_main_ui:
                        continue
                    violations.append(
                        f"Boundary violation in {py_file.relative_to(src_skylock)}: "
                        f"package '{pkg_name}' cannot import 'skylock.{imported_sub}'"
                    )

                # Special check: no module may import skylock.ui except ui itself or app.main lazily
                if imported_sub == "ui" and pkg_name != "ui" and not is_lazy_app_main_ui:
                    violations.append(
                        f"UI leak in {py_file.relative_to(src_skylock)}: "
                        "cannot import skylock.ui (only skylock.app.main lazily inside function)"
                    )

    assert not violations, "Import boundary violations found:\n" + "\n".join(violations)
