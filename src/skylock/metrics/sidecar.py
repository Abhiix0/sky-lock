"""Ground truth sidecar CSV loader for external video (MP4) evaluation.

Lives strictly inside metrics/ to preserve the ground-truth firewall.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

from skylock.core.types import GroundTruthSample, Pointing, TargetTruth


class GroundTruthSidecar:
    """Loads and provides ground-truth annotations from external CSV sidecars.

    Expected CSV header format:
        frame,x,y,visible
    """

    def __init__(
        self,
        samples: dict[int, GroundTruthSample],
    ) -> None:
        """Initialize with mapping of frame index to GroundTruthSample."""
        self._samples = samples

    @classmethod
    def load(
        cls,
        path: str | Path,
        boresight_px: tuple[float, float] = (320.0, 240.0),
        fps: float = 30.0,
    ) -> GroundTruthSidecar:
        """Load sidecar CSV file into GroundTruthSidecar instance.

        Args:
            path: Path to CSV file.
            boresight_px: Principal point (cx, cy) in pixels.
            fps: Frame rate for timestamp derivation.

        Returns:
            GroundTruthSidecar instance.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Ground truth sidecar file not found: {path}")

        samples: dict[int, GroundTruthSample] = {}
        cx, cy = boresight_px

        with open(p, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise ValueError(f"Empty sidecar CSV: {path}")

            # Normalize column names
            col_map = {col.strip().lower(): col for col in reader.fieldnames}
            for required in ("frame", "x", "y", "visible"):
                if required not in col_map:
                    raise ValueError(
                        f"Missing required column '{required}' in sidecar CSV {path}. "
                        f"Found: {reader.fieldnames}"
                    )

            frame_col = col_map["frame"]
            x_col = col_map["x"]
            y_col = col_map["y"]
            vis_col = col_map["visible"]

            for row in reader:
                frame_idx = int(row[frame_col])
                x = float(row[x_col])
                y = float(row[y_col])
                vis_raw = row[vis_col].strip().lower()
                visible = vis_raw in ("1", "true", "t", "yes")

                timestamp_s = float(frame_idx / fps) if fps > 0.0 else 0.0
                boresight_err = float(math.hypot(x - cx, y - cy)) if visible else None

                target_truth = TargetTruth(
                    id="primary",
                    az_deg=0.0,
                    el_deg=0.0,
                    px=x,
                    py=y,
                    visible=visible,
                    in_fov=True,
                )

                sample = GroundTruthSample(
                    frame_index=frame_idx,
                    timestamp_s=timestamp_s,
                    targets=(target_truth,),
                    primary_px=(x, y) if visible else None,
                    primary_visible=visible,
                    boresight_error_px=boresight_err,
                    pointing=Pointing(pan_deg=0.0, tilt_deg=0.0),
                    disturbance_offset_px=(0.0, 0.0),
                )
                samples[frame_idx] = sample

        return cls(samples=samples)

    def get(self, frame_index: int) -> GroundTruthSample | None:
        """Retrieve ground truth sample for a given frame index."""
        return self._samples.get(frame_index)

    def __getitem__(self, frame_index: int) -> GroundTruthSample:
        return self._samples[frame_index]

    def __contains__(self, frame_index: int) -> bool:
        return frame_index in self._samples

    def __len__(self) -> int:
        return len(self._samples)
