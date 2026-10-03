"""Ground-truth firewall validation tests.

(a) Poisoned-truth determinism: run the same scenario twice but corrupt the
    GroundTruthSample values returned by the source after rendering.
    The PipelineOutput sequences must be bit-identical, proving that the
    pipeline never consumes ground truth.

(b) AST scan: verify that no module inside vision/, tracking/, control/, or
    core/pipeline.py imports from skylock.simulation or skylock.metrics, and
    that none of them reference the identifier 'GroundTruthSample'.
"""

from __future__ import annotations

import ast
from pathlib import Path

from skylock.app.session import Session
from skylock.config.io import override
from skylock.config.presets import spec_default
from skylock.core.types import (
    GroundTruthSample,
    Pointing,
    StepResult,
    TargetTruth,
)
from skylock.simulation.source import SimulationSource

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SRC_ROOT = Path(__file__).parents[3] / "src" / "skylock"


def _build_clean_cfg(seed: int = 42):
    """Build a simple clean-scene config for firewall tests."""
    base = spec_default()
    return override(
        base,
        {
            "seed": seed,
            "target.count": 1,
            "target.targets": [
                {
                    "id": "t0",
                    "size_px": 10,
                    "shape": "disc",
                    "brightness": 220.0,
                    "initial": "fixed",
                    "initial_pos_deg": [2.0, 1.0],
                    "motion": {"kind": "line", "speed_deg_s": 0.3, "heading_deg": 0.0},
                }
            ],
        },
    )


def _corrupt_truth(truth: GroundTruthSample) -> GroundTruthSample:
    """Return a new GroundTruthSample with every numeric field corrupted to nonsense values."""
    corrupted_targets = tuple(
        TargetTruth(
            id=tt.id,
            az_deg=tt.az_deg + 99999.0,
            el_deg=tt.el_deg - 99999.0,
            px=tt.px + 50000.0,
            py=tt.py - 50000.0,
            visible=not tt.visible,  # flip visibility too
            in_fov=not tt.in_fov,
        )
        for tt in truth.targets
    )
    return GroundTruthSample(
        frame_index=truth.frame_index,
        timestamp_s=truth.timestamp_s,
        targets=corrupted_targets,
        primary_px=(truth.primary_px[0] + 50000.0, truth.primary_px[1] - 50000.0)
        if truth.primary_px is not None
        else None,
        primary_visible=not truth.primary_visible,
        boresight_error_px=99999.9 if truth.boresight_error_px is not None else None,
        pointing=Pointing(pan_deg=truth.pointing.pan_deg + 180.0, tilt_deg=-90.0),
        disturbance_offset_px=(50000.0, -50000.0),
    )


class _PoisonedSource:
    """Wraps SimulationSource but corrupts GroundTruthSample before returning it.

    The underlying Frame (with actual pixel data) is returned unmodified.
    """

    def __init__(self, source: SimulationSource) -> None:
        self._source = source

    # Delegate FrameSource properties
    @property
    def width(self) -> int:
        return self._source.width

    @property
    def height(self) -> int:
        return self._source.height

    @property
    def fps(self) -> float:
        return self._source.fps

    @property
    def source_id(self) -> str:
        return self._source.source_id

    @property
    def kind(self):
        return self._source.kind

    @property
    def gimbal(self):
        return self._source.gimbal

    def open(self) -> None:
        self._source.open()

    def read(self):
        return self._source.read()

    def read_with_truth(self):
        frame, truth = self._source.read_with_truth()
        return frame, _corrupt_truth(truth)

    def reset(self) -> None:
        self._source.reset()

    def close(self) -> None:
        self._source.close()


def _pipeline_output_key(step: StepResult) -> tuple:
    """Deterministic comparison key from PipelineOutput (excludes wall-clock latency_ms)."""
    out = step.output
    est = out.estimate
    return (
        out.frame_index,
        out.state,
        round(est.px, 6) if est is not None else None,
        round(est.py, 6) if est is not None else None,
        round(est.pan_deg, 9) if est is not None else None,
        round(est.tilt_deg, 9) if est is not None else None,
        len(out.detections),
        out.intent.mode,
    )


# ---------------------------------------------------------------------------
# (a) Poisoned-truth determinism test
# ---------------------------------------------------------------------------

def test_poisoned_truth_pipeline_identical() -> None:
    """Corrupting GroundTruthSample must not change the PipelineOutput sequence."""
    cfg = _build_clean_cfg(seed=42)

    # Run 1: normal source
    from skylock.app.factory import create_session_components
    from skylock.simulation.source import SimulationSource

    src1, pip1, ctrl1 = create_session_components(cfg)
    session1 = Session(cfg, source=src1, pipeline=pip1, controller=ctrl1)
    session1.source.open()
    results1 = session1.run(seconds=4.0)

    # Run 2: poisoned source wrapping a fresh SimulationSource
    from skylock.simulation.gimbal import VirtualGimbal

    gimbal2 = VirtualGimbal(cfg.gimbal)
    raw_source2 = SimulationSource(cfg, gimbal=gimbal2)
    poisoned_src = _PoisonedSource(raw_source2)

    from skylock.control.controller import PointingController
    from skylock.core.pipeline import TrackingPipeline

    pip2 = TrackingPipeline(cfg)
    ctrl2 = PointingController(
        cfg.control, cfg.camera,
        max_slew_rate_deg_s=cfg.gimbal.slew_rate_deg_s,
    )
    session2 = Session(cfg, source=poisoned_src, pipeline=pip2, controller=ctrl2)
    session2.source.open()
    results2 = session2.run(seconds=4.0)

    assert len(results1) == len(results2), (
        f"Runs produced different frame counts: {len(results1)} vs {len(results2)}"
    )

    mismatches = []
    for i, (s1, s2) in enumerate(zip(results1, results2, strict=True)):
        k1 = _pipeline_output_key(s1)
        k2 = _pipeline_output_key(s2)
        if k1 != k2:
            mismatches.append((i, k1, k2))

    assert not mismatches, (
        f"Pipeline outputs differ between normal and poisoned-truth runs at "
        f"{len(mismatches)} frames. First 3 mismatches:\n"
        + "\n".join(f"  frame {i}: normal={k1!r}  poisoned={k2!r}" for i, k1, k2 in mismatches[:3])
    )


def test_poisoned_truth_truth_values_are_different() -> None:
    """Sanity check: the corrupted truth values really do differ from the originals."""
    cfg = _build_clean_cfg(seed=42)

    from skylock.simulation.gimbal import VirtualGimbal
    from skylock.simulation.source import SimulationSource as SS

    gimbal = VirtualGimbal(cfg.gimbal)
    source = SS(cfg, gimbal=gimbal)
    source.open()
    frame, truth = source.read_with_truth()

    corrupted = _corrupt_truth(truth)
    if truth.primary_px is not None and corrupted.primary_px is not None:
        assert truth.primary_px != corrupted.primary_px, "Corruption did not change primary_px"
    assert truth.primary_visible != corrupted.primary_visible, "Corruption did not flip visibility"
    source.close()


# ---------------------------------------------------------------------------
# (b) AST scan: no GroundTruthSample in vision/tracking/control/core/pipeline.py
# ---------------------------------------------------------------------------

# Packages whose source files must not contain GroundTruthSample references
_FORBIDDEN_PACKAGES = [
    "vision",
    "tracking",
    "control",
]

# Individual files that are also prohibited
_FORBIDDEN_FILES = [
    SRC_ROOT / "core" / "pipeline.py",
]


def _collect_py_files(package_dir: Path) -> list[Path]:
    return sorted(package_dir.rglob("*.py"))


def _file_references_symbol(path: Path, symbol: str) -> bool:
    """Return True if the AST of the file contains any reference to `symbol` as an identifier."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        # Import: `import skylock.simulation` or `from skylock.simulation import ...`
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                if alias.name == symbol or alias.asname == symbol:
                    return True
                # `from skylock.x import GroundTruthSample`
                if symbol in module:
                    return True
        if isinstance(node, ast.Import):
            for alias in node.names:
                if symbol in (alias.name or "") or symbol in (alias.asname or ""):
                    return True
        # Any Name node whose identifier matches
        if isinstance(node, ast.Name) and node.id == symbol:
            return True
        if isinstance(node, ast.Attribute) and node.attr == symbol:
            return True

    return False


def _file_imports_forbidden_modules(path: Path, forbidden_prefixes: list[str]) -> list[str]:
    """Return list of forbidden import statements found in the file's AST."""
    violations: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for prefix in forbidden_prefixes:
                if module == prefix or module.startswith(f"{prefix}."):
                    violations.append(f"  from {module} import ... (line {node.lineno})")
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name or ""
                for prefix in forbidden_prefixes:
                    if name == prefix or name.startswith(f"{prefix}."):
                        violations.append(f"  import {name} (line {node.lineno})")

    return violations


def test_ast_no_ground_truth_in_pipeline_packages() -> None:
    """vision/, tracking/, control/, and core/pipeline.py must not reference GroundTruthSample."""
    violations: list[str] = []

    # Check forbidden packages
    for pkg_name in _FORBIDDEN_PACKAGES:
        pkg_dir = SRC_ROOT / pkg_name
        if not pkg_dir.exists():
            continue
        for py_file in _collect_py_files(pkg_dir):
            if _file_references_symbol(py_file, "GroundTruthSample"):
                rel = py_file.relative_to(SRC_ROOT)
                violations.append(f"  {rel}")

    # Check individual forbidden files
    for ff in _FORBIDDEN_FILES:
        if ff.exists() and _file_references_symbol(ff, "GroundTruthSample"):
            rel = ff.relative_to(SRC_ROOT)
            violations.append(f"  {rel}")

    assert not violations, (
        "GroundTruthSample referenced in non-metrics packages:\n" + "\n".join(violations)
    )


def test_ast_no_simulation_import_in_pipeline_packages() -> None:
    """vision/, tracking/, control/, core/pipeline.py must not import skylock.simulation."""
    forbidden_module_prefixes = ["skylock.simulation"]
    violations: list[str] = []

    for pkg_name in _FORBIDDEN_PACKAGES:
        pkg_dir = SRC_ROOT / pkg_name
        if not pkg_dir.exists():
            continue
        for py_file in _collect_py_files(pkg_dir):
            found = _file_imports_forbidden_modules(py_file, forbidden_module_prefixes)
            if found:
                rel = py_file.relative_to(SRC_ROOT)
                violations.append(f"  {rel}:\n" + "\n".join(found))

    for ff in _FORBIDDEN_FILES:
        if ff.exists():
            found = _file_imports_forbidden_modules(ff, forbidden_module_prefixes)
            if found:
                rel = ff.relative_to(SRC_ROOT)
                violations.append(f"  {rel}:\n" + "\n".join(found))

    assert not violations, (
        "Forbidden skylock.simulation import in pipeline packages:\n" + "\n".join(violations)
    )


def test_ast_no_metrics_import_in_pipeline_packages() -> None:
    """vision/, tracking/, control/, core/pipeline.py must not import skylock.metrics."""
    forbidden_module_prefixes = ["skylock.metrics"]
    violations: list[str] = []

    for pkg_name in _FORBIDDEN_PACKAGES:
        pkg_dir = SRC_ROOT / pkg_name
        if not pkg_dir.exists():
            continue
        for py_file in _collect_py_files(pkg_dir):
            found = _file_imports_forbidden_modules(py_file, forbidden_module_prefixes)
            if found:
                rel = py_file.relative_to(SRC_ROOT)
                violations.append(f"  {rel}:\n" + "\n".join(found))

    for ff in _FORBIDDEN_FILES:
        if ff.exists():
            found = _file_imports_forbidden_modules(ff, forbidden_module_prefixes)
            if found:
                rel = ff.relative_to(SRC_ROOT)
                violations.append(f"  {rel}:\n" + "\n".join(found))

    assert not violations, (
        "Forbidden skylock.metrics import in pipeline packages:\n" + "\n".join(violations)
    )
