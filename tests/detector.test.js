import { describe, it, expect } from 'vitest';
import { createDetector } from '../src/tracking/detector.js';

/**
 * Helper to create synthetic 640x480 bottom-up RGBA frame.
 */
function createSyntheticFrame(width = 640, height = 480) {
  const data = new Uint8Array(width * height * 4);
  return {
    width,
    height,
    data,
    timestamp: 0,
    frameId: 1
  };
}

/**
 * Set pixel in frame using top-left coordinates (translates to bottom-up).
 */
function setPixel(frame, x, y, r, g, b, a = 255) {
  const rawY = (frame.height - 1) - y;
  const idx = (rawY * frame.width + x) * 4;
  frame.data[idx] = r;
  frame.data[idx + 1] = g;
  frame.data[idx + 2] = b;
  frame.data[idx + 3] = a;
}

/**
 * Stamp a 2D Gaussian magenta blob centered at (targetX, targetY).
 */
function stampGaussianBlob(frame, targetX, targetY, sigma = 1.5, peakColor = [255, 30, 255]) {
  const radius = Math.ceil(sigma * 3);
  const minX = Math.max(0, Math.floor(targetX - radius));
  const maxX = Math.min(frame.width - 1, Math.ceil(targetX + radius));
  const minY = Math.max(0, Math.floor(targetY - radius));
  const maxY = Math.min(frame.height - 1, Math.ceil(targetY + radius));

  for (let y = minY; y <= maxY; y++) {
    for (let x = minX; x <= maxX; x++) {
      const dx = x - targetX;
      const dy = y - targetY;
      const d2 = dx * dx + dy * dy;
      const w = Math.exp(-d2 / (2 * sigma * sigma));
      if (w > 0.05) {
        setPixel(
          frame,
          x,
          y,
          Math.round(peakColor[0] * w),
          Math.round(peakColor[1] * w),
          Math.round(peakColor[2] * w)
        );
      }
    }
  }
}

describe('Detector (Sub-phase 2A)', () => {
  const detector = createDetector();

  it('(a) single Gaussian magenta blob at known subpixel position: centroid error < 0.2 px', () => {
    const frame = createSyntheticFrame(640, 480);
    const targetX = 320.4;
    const targetY = 240.6;
    stampGaussianBlob(frame, targetX, targetY, 2.0);

    const result = detector.detect(frame);
    expect(result.blobs.length).toBe(1);

    const blob = result.blobs[0];
    const errX = Math.abs(blob.cx - targetX);
    const errY = Math.abs(blob.cy - targetY);
    expect(errX).toBeLessThan(0.2);
    expect(errY).toBeLessThan(0.2);
  });

  it('(b) large white cloud region plus blob: only blob returned in chroma mode', () => {
    const frame = createSyntheticFrame(640, 480);

    // Draw large white cloud: R=240, G=240, B=240 => chroma = min(240,240)-240 = 0
    for (let y = 100; y < 200; y++) {
      for (let x = 100; x < 250; x++) {
        setPixel(frame, x, y, 240, 240, 240);
      }
    }

    // Add saturated magenta beacon
    stampGaussianBlob(frame, 350.0, 300.0, 2.0);

    const result = detector.detect(frame);
    expect(result.blobs.length).toBe(1);
    expect(Math.abs(result.blobs[0].cx - 350.0)).toBeLessThan(0.3);
  });

  it('(c) empty black frame: zero blobs', () => {
    const frame = createSyntheticFrame(640, 480);
    const result = detector.detect(frame);
    expect(result.blobs.length).toBe(0);
  });

  it('(d) two blobs: both returned, stronger first', () => {
    const frame = createSyntheticFrame(640, 480);
    // Blob 1: peak magenta (255, 20, 255) -> chroma 235
    stampGaussianBlob(frame, 200, 200, 2.0, [255, 20, 255]);
    // Blob 2: dimmer magenta (180, 20, 180) -> chroma 160
    stampGaussianBlob(frame, 400, 200, 2.0, [180, 20, 180]);

    const result = detector.detect(frame);
    expect(result.blobs.length).toBe(2);
    expect(result.blobs[0].peak).toBeGreaterThan(result.blobs[1].peak);
    expect(Math.abs(result.blobs[0].cx - 200)).toBeLessThan(0.5);
    expect(Math.abs(result.blobs[1].cx - 400)).toBeLessThan(0.5);
  });

  it('(e) row-order check: blob near TOP of image comes back with small y', () => {
    const frame = createSyntheticFrame(640, 480);
    // Top of image means small top-left y, e.g. y = 15
    stampGaussianBlob(frame, 320, 15, 2.0);

    const result = detector.detect(frame);
    expect(result.blobs.length).toBe(1);
    expect(result.blobs[0].cy).toBeLessThan(30);
  });

  it('(f) speed: 640x480 frame with one blob, median detect() under 3 ms', () => {
    const frame = createSyntheticFrame(640, 480);
    stampGaussianBlob(frame, 320, 240, 2.0);

    // Warm-up runs
    for (let i = 0; i < 5; i++) {
      detector.detect(frame);
    }

    const times = [];
    const iterations = 50;
    for (let i = 0; i < iterations; i++) {
      const res = detector.detect(frame);
      times.push(res.processingMs);
    }

    times.sort((a, b) => a - b);
    const medianMs = times[Math.floor(times.length / 2)];
    console.log(`Measured median detect() latency: ${medianMs.toFixed(3)} ms`);
    expect(medianMs).toBeLessThan(3.0);
  });
});
