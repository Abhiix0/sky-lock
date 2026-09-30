"""Authoritative requirement evaluation producing tri-state verdicts against specification."""

from __future__ import annotations

from skylock.config.models import RequirementsConfig
from skylock.core.enums import MetricStatus, Verdict
from skylock.metrics.status import RunMetrics


def evaluate(run_metrics: RunMetrics, req: RequirementsConfig) -> dict[str, Verdict]:
    """Evaluate consolidated run metrics against requirements specification.

    Evaluation rules:
    - Non-MEASURED metrics result in INDETERMINATE (never PASS).
    - Special rule: acquisition is FAIL (not INDETERMINATE) when the run had a full
      observable window >= acquisition_max_s and never reached TRACK.
    - Overall verdict: FAIL if any is FAIL; else INDETERMINATE if any is INDETERMINATE;
      else PASS only when all evaluated requirements are PASS.

    Args:
        run_metrics: Consolidated metrics from MetricsCollector.finalize().
        req: Requirements configuration criteria.

    Returns:
        Mapping of requirement name to Verdict (PASS, FAIL, or INDETERMINATE).
    """
    verdicts: dict[str, Verdict] = {}

    # 1. Acquisition Time (PS_SPEC §7: <= 2.0 s)
    acq_m = run_metrics.acquisition_time_from_observable_s
    if acq_m.status == MetricStatus.MEASURED and acq_m.value is not None:
        if acq_m.value <= req.acquisition_max_s:
            verdicts["acquisition_time"] = Verdict.PASS
        else:
            verdicts["acquisition_time"] = Verdict.FAIL
    else:
        # Rule: acquisition is FAIL when observable window >= acquisition_max_s
        # and never reached TRACK
        never_acquired = (
            run_metrics.acquisition_time_from_observable_s.status == MetricStatus.NOT_ACQUIRED
            or run_metrics.acquisition_time_from_start_s.status == MetricStatus.NOT_ACQUIRED
        )
        if run_metrics.observable_duration_s >= req.acquisition_max_s and never_acquired:
            verdicts["acquisition_time"] = Verdict.FAIL
        else:
            verdicts["acquisition_time"] = Verdict.INDETERMINATE

    # 2. Tracking Error (PS_SPEC §7: <= 10.0 px)
    trk_m = run_metrics.tracking_error_px
    if trk_m.status == MetricStatus.MEASURED and trk_m.value is not None:
        stat_name = req.tracking_error_statistic.lower()
        stat_val = getattr(trk_m.value, stat_name, trk_m.value.rms)
        if stat_val <= req.tracking_error_px_max:
            verdicts["tracking_error"] = Verdict.PASS
        else:
            verdicts["tracking_error"] = Verdict.FAIL
    else:
        verdicts["tracking_error"] = Verdict.INDETERMINATE

    # 3. Target Loss Rate (PS_SPEC §7: < 5%)
    loss_m = run_metrics.target_loss_rate
    if loss_m.status == MetricStatus.MEASURED and loss_m.value is not None:
        if loss_m.value <= req.target_loss_rate_max:
            verdicts["target_loss_rate"] = Verdict.PASS
        else:
            verdicts["target_loss_rate"] = Verdict.FAIL
    else:
        verdicts["target_loss_rate"] = Verdict.INDETERMINATE

    # 4. Reacquisition Time (PS_SPEC §7: <= 1.0 s)
    reacq_m = run_metrics.reacquisition_time_s
    if reacq_m.status == MetricStatus.MEASURED and reacq_m.value is not None:
        if reacq_m.value.max_s <= req.reacquisition_max_s:
            verdicts["reacquisition_time"] = Verdict.PASS
        else:
            verdicts["reacquisition_time"] = Verdict.FAIL
    elif reacq_m.status == MetricStatus.FAILED:
        verdicts["reacquisition_time"] = Verdict.FAIL
    else:
        verdicts["reacquisition_time"] = Verdict.INDETERMINATE

    # 5. Processing FPS (PS_SPEC §7: >= 20.0 FPS)
    fps_m = run_metrics.fps_pipeline
    if fps_m.status == MetricStatus.MEASURED and fps_m.value is not None:
        if fps_m.value >= req.processing_fps_min:
            verdicts["processing_fps"] = Verdict.PASS
        else:
            verdicts["processing_fps"] = Verdict.FAIL
    else:
        verdicts["processing_fps"] = Verdict.INDETERMINATE

    # Overall Verdict
    indiv = list(verdicts.values())
    if any(v == Verdict.FAIL for v in indiv):
        overall = Verdict.FAIL
    elif any(v == Verdict.INDETERMINATE for v in indiv):
        overall = Verdict.INDETERMINATE
    else:
        overall = Verdict.PASS

    verdicts["overall"] = overall
    return verdicts
