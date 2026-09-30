/**
 * Benchmark Scenario Definitions for Sky Lock.
 * Defines standard reproducible evaluation benchmarks spanning clean, disturbance,
 * optical decoy, multi-speed, and actuator slew stress conditions.
 */

export const BENCHMARK_SEEDS = [1, 2, 3];

export const SCENARIOS = [
  {
    id: 'S0',
    name: 'Clean Baseline',
    durationSimSec: 190, // ~3 orbit cycles
    disturbancePreset: 'OFF',
    decoys: false,
    simSpeed: 1,
    slewPreset: 'baseline'
  },
  {
    id: 'S1',
    name: 'Low Disturbances',
    durationSimSec: 190,
    disturbancePreset: 'LOW',
    decoys: false,
    simSpeed: 1,
    slewPreset: 'baseline'
  },
  {
    id: 'S2',
    name: 'Medium Disturbances',
    durationSimSec: 190,
    disturbancePreset: 'MED',
    decoys: false,
    simSpeed: 1,
    slewPreset: 'baseline'
  },
  {
    id: 'S3',
    name: 'High Disturbances',
    durationSimSec: 190,
    disturbancePreset: 'HIGH',
    decoys: false,
    simSpeed: 1,
    slewPreset: 'baseline'
  },
  {
    id: 'S4',
    name: 'Medium + 3 Decoys',
    durationSimSec: 190,
    disturbancePreset: 'MED',
    decoys: true,
    decoyCount: 3,
    simSpeed: 1,
    slewPreset: 'baseline'
  },
  {
    id: 'S5',
    name: 'Occlusion at 4x Speed',
    durationSimSec: 190,
    disturbancePreset: 'OFF',
    decoys: false,
    simSpeed: 4,
    slewPreset: 'baseline'
  },
  {
    id: 'S6',
    name: 'PS-Slew (30°/s) Stress',
    durationSimSec: 190,
    disturbancePreset: 'OFF',
    decoys: false,
    simSpeed: 1,
    slewPreset: 'ps'
  },
  {
    id: 'S7',
    name: 'High + Decoys Stress',
    durationSimSec: 190,
    disturbancePreset: 'HIGH',
    decoys: true,
    decoyCount: 3,
    simSpeed: 1,
    slewPreset: 'baseline'
  }
];
