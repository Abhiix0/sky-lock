import { describe, it, expect } from 'vitest';
import { SCENARIOS, BENCHMARK_SEEDS } from '../src/tracking/scenarios.js';
import { computeMeanStd, computeAggregateTable, formatBenchmarkCsv } from '../src/tracking/exporter.js';

describe('Benchmark and Scenarios (Sub-phase 3D)', () => {
  it('defines all 8 standard scenarios S0 to S7 with required attributes', () => {
    expect(SCENARIOS.length).toBe(8);
    expect(BENCHMARK_SEEDS).toEqual([1, 2, 3]);

    const ids = SCENARIOS.map((s) => s.id);
    expect(ids).toEqual(['S0', 'S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7']);

    SCENARIOS.forEach((sc) => {
      expect(sc.durationSimSec).toBeGreaterThanOrEqual(60);
      expect(['OFF', 'LOW', 'MED', 'HIGH']).toContain(sc.disturbancePreset);
      expect(['baseline', 'ps']).toContain(sc.slewPreset);
      expect(typeof sc.decoys).toBe('boolean');
    });
  });

  it('computes mean and standard deviation accurately', () => {
    const data = [10, 20, 30, 40, 50];
    const { mean, std } = computeMeanStd(data);
    expect(mean).toBe(30);
    // Sample variance of [10, 20, 30, 40, 50] with n-1:
    // (400 + 100 + 0 + 100 + 400) / 4 = 250 -> std = sqrt(250) = 15.811
    expect(std).toBeCloseTo(15.811, 2);
  });

  it('aggregates multi-seed scenario runs into summary table', () => {
    const mockRuns = [
      {
        scenario: { id: 'S0', name: 'Clean', seed: 1 },
        summary: { lockRetentionRate: 98.0, pointingError: { rmsPx: 4.0 }, acquisitionTimeSec: 2.0, reacquisitionMeanSec: 1.0, processingMs: { mean: 1.2 }, falseLocks: 0 }
      },
      {
        scenario: { id: 'S0', name: 'Clean', seed: 2 },
        summary: { lockRetentionRate: 96.0, pointingError: { rmsPx: 4.4 }, acquisitionTimeSec: 2.2, reacquisitionMeanSec: 1.1, processingMs: { mean: 1.4 }, falseLocks: 0 }
      },
      {
        scenario: { id: 'S1', name: 'Low', seed: 1 },
        summary: { lockRetentionRate: 94.0, pointingError: { rmsPx: 5.5 }, acquisitionTimeSec: 2.5, reacquisitionMeanSec: 1.5, processingMs: { mean: 1.5 }, falseLocks: 0 }
      }
    ];

    const agg = computeAggregateTable(mockRuns);
    expect(agg.S0).toBeDefined();
    expect(agg.S0.retention.mean).toBe(97.0);
    expect(agg.S0.retention.std).toBeCloseTo(1.414, 2);
    expect(agg.S0.pointingRmsPx.mean).toBe(4.2);
    expect(agg.S1).toBeDefined();
    expect(agg.S1.retention.mean).toBe(94.0);
  });

  it('formats benchmark runs as valid CSV matching BENCHMARK_SCHEMA.md', () => {
    const mockRuns = [
      {
        scenario: { id: 'S2', name: 'Medium Disturbances', seed: 42, durationSimSec: 190, simSpeed: 1, disturbancePreset: 'MED', decoys: false, slewPreset: 'baseline' },
        summary: {
          observableTimeSec: 175.2,
          inTrackTimeSec: 150.0,
          lockRetentionRate: 85.6,
          acquisitionTimeSec: 2.1,
          acquisitionFromStartSec: 7.2,
          reacquisitions: [2.5, 2.7],
          reacquisitionMeanSec: 2.6,
          reacquisitionMaxSec: 2.7,
          pointingError: { meanPx: 5.2, rmsPx: 7.1, p95Px: 12.0, maxPx: 25.0, meanMrad: 2.27, rmsMrad: 3.10, p95Mrad: 5.23 },
          trackingError: { meanPx: 1.2, rmsPx: 1.8 },
          falseLocks: 0,
          processingMs: { mean: 1.3, p95: 2.1 },
          fps: { mean: 59.8 },
          droppedFrames: 3
        },
        wallClockMs: 1450.5
      }
    ];

    const csv = formatBenchmarkCsv(mockRuns);
    const lines = csv.split('\n');
    expect(lines.length).toBe(2);

    const headers = lines[0].split(',');
    expect(headers).toContain('scenario_id');
    expect(headers).toContain('lock_retention_pct');
    expect(headers).toContain('pointing_err_rms_px');
    expect(headers).toContain('pointing_err_rms_mrad');
    expect(headers).toContain('false_locks');
    expect(headers).toContain('reacq_mean_sec');

    const row = lines[1].split(',');
    expect(row[0]).toBe('S2');
    expect(row[1]).toBe('Medium Disturbances');
    expect(row[2]).toBe('42');
    expect(row[11]).toBe('85.60'); // lock_retention_pct
  });
});
