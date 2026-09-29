import { DETECTOR_CONFIG } from './config.js';

/**
 * Creates the beacon blob detector.
 *
 * @param {Object} [config=DETECTOR_CONFIG]
 * @returns {Object} Detector instance with detect(frame, opts?)
 */
export function createDetector(config = DETECTOR_CONFIG) {
  const cfg = { ...DETECTOR_CONFIG, ...config };

  // Pre-allocated static buffers sized for up to 640x480
  const maxPixels = 640 * 480;
  const sparseIndices = new Int32Array(maxPixels);
  const sparseScores = new Float32Array(maxPixels);
  const pixelToActiveIdx = new Int32Array(maxPixels);
  pixelToActiveIdx.fill(-1);

  // Disjoint set union-find structures
  const parent = new Int32Array(maxPixels);
  const rank = new Int32Array(maxPixels);

  // Blob accumulation structures
  const maxBlobCandidates = 1024;
  const blobRootToIdx = new Int32Array(maxPixels);
  blobRootToIdx.fill(-1);

  const blobArea = new Int32Array(maxBlobCandidates);
  const blobSumWeight = new Float64Array(maxBlobCandidates);
  const blobSumX = new Float64Array(maxBlobCandidates);
  const blobSumY = new Float64Array(maxBlobCandidates);
  const blobPeak = new Float32Array(maxBlobCandidates);
  const blobMinX = new Int32Array(maxBlobCandidates);
  const blobMaxX = new Int32Array(maxBlobCandidates);
  const blobMinY = new Int32Array(maxBlobCandidates);
  const blobMaxY = new Int32Array(maxBlobCandidates);

  function find(i) {
    let root = i;
    while (root !== parent[root]) {
      root = parent[root];
    }
    let curr = i;
    while (curr !== root) {
      const nxt = parent[curr];
      parent[curr] = root;
      curr = nxt;
    }
    return root;
  }

  function union(i, j) {
    const rootI = find(i);
    const rootJ = find(j);
    if (rootI === rootJ) return;

    if (rank[rootI] < rank[rootJ]) {
      parent[rootI] = rootJ;
    } else if (rank[rootI] > rank[rootJ]) {
      parent[rootJ] = rootI;
    } else {
      parent[rootJ] = rootI;
      rank[rootI]++;
    }
  }

  /**
   * Detect beacon blob centroids in the camera frame.
   *
   * @param {Object} frame - Camera frame { width, height, data, timestamp, frameId }
   * @param {Object} [opts] - Optional detection options (e.g. { roi: {x,y,w,h} })
   * @returns {{ blobs: Array<{ cx: number, cy: number, area: number, peak: number, snr: number, bbox: {x0: number, y0: number, x1: number, y1: number} }>, processingMs: number }}
   */
  function detect(frame, opts = {}) {
    const t0 = typeof performance !== 'undefined' ? performance.now() : Date.now();

    if (!frame || !frame.data || frame.width <= 0 || frame.height <= 0) {
      return { blobs: [], processingMs: 0 };
    }

    const { width, height, data } = frame;
    const isChroma = (opts.mode || cfg.mode) === 'chroma';
    const threshold = isChroma
      ? (opts.chromaThreshold ?? cfg.chromaThreshold)
      : (opts.lumaThreshold ?? cfg.lumaThreshold);

    // Determine ROI in top-left coordinates
    let minX = 0;
    let maxX = width - 1;
    let minY = 0;
    let maxY = height - 1;

    if (opts.roi) {
      minX = Math.max(0, Math.floor(opts.roi.x));
      maxX = Math.min(width - 1, Math.ceil(opts.roi.x + opts.roi.w));
      minY = Math.max(0, Math.floor(opts.roi.y));
      maxY = Math.min(height - 1, Math.ceil(opts.roi.y + opts.roi.h));
    }

    // Step 1: Subsample ~1% of pixels for background stats
    let bgSum = 0;
    let bgSumSq = 0;
    let bgCount = 0;
    const stepX = 16;
    const stepY = 16;

    for (let y = 0; y < height; y += stepY) {
      const rawY = height - 1 - y;
      const rowOffset = rawY * width * 4;
      for (let x = 0; x < width; x += stepX) {
        const idx = rowOffset + x * 4;
        const r = data[idx];
        const g = data[idx + 1];
        const b = data[idx + 2];
        const s = isChroma ? (r < b ? r : b) - g : 0.299 * r + 0.587 * g + 0.114 * b;
        bgSum += s;
        bgSumSq += s * s;
        bgCount++;
      }
    }

    const bgMean = bgCount > 0 ? bgSum / bgCount : 0;
    const bgVariance = bgCount > 0 ? Math.max(0, bgSumSq / bgCount - bgMean * bgMean) : 0;
    const bgStd = Math.sqrt(bgVariance);

    // Step 2: Pass 1 - Collect pixels above threshold & initialize disjoint sets
    let numActive = 0;

    for (let y = minY; y <= maxY; y++) {
      const rawY = height - 1 - y;
      const rowOffset = rawY * width * 4;
      let idx = rowOffset + minX * 4;

      for (let x = minX; x <= maxX; x++, idx += 4) {
        const r = data[idx];
        const g = data[idx + 1];
        const b = data[idx + 2];
        const score = isChroma ? (r < b ? r : b) - g : 0.299 * r + 0.587 * g + 0.114 * b;

        if (score >= threshold) {
          const pixelIdx = y * width + x;
          const activeIdx = numActive++;

          sparseIndices[activeIdx] = pixelIdx;
          sparseScores[activeIdx] = score;
          pixelToActiveIdx[pixelIdx] = activeIdx;

          parent[activeIdx] = activeIdx;
          rank[activeIdx] = 0;

          // 4-connectivity: check left and top neighbors
          if (x > minX) {
            const leftActive = pixelToActiveIdx[pixelIdx - 1];
            if (leftActive !== -1) {
              union(activeIdx, leftActive);
            }
          }
          if (y > minY) {
            const topActive = pixelToActiveIdx[pixelIdx - width];
            if (topActive !== -1) {
              union(activeIdx, topActive);
            }
          }
        }
      }
    }

    // Step 3: Pass 2 - Aggregate connected components
    let numBlobs = 0;

    for (let i = 0; i < numActive; i++) {
      const root = find(i);
      let blobIdx = blobRootToIdx[root];

      const pIdx = sparseIndices[i];
      const px = pIdx % width;
      const py = Math.floor(pIdx / width);
      const score = sparseScores[i];

      if (blobIdx === -1) {
        if (numBlobs >= maxBlobCandidates) continue;
        blobIdx = numBlobs++;
        blobRootToIdx[root] = blobIdx;

        blobArea[blobIdx] = 1;
        blobSumWeight[blobIdx] = score;
        blobSumX[blobIdx] = px * score;
        blobSumY[blobIdx] = py * score;
        blobPeak[blobIdx] = score;
        blobMinX[blobIdx] = px;
        blobMaxX[blobIdx] = px;
        blobMinY[blobIdx] = py;
        blobMaxY[blobIdx] = py;
      } else {
        blobArea[blobIdx]++;
        blobSumWeight[blobIdx] += score;
        blobSumX[blobIdx] += px * score;
        blobSumY[blobIdx] += py * score;
        if (score > blobPeak[blobIdx]) {
          blobPeak[blobIdx] = score;
        }
        if (px < blobMinX[blobIdx]) blobMinX[blobIdx] = px;
        if (px > blobMaxX[blobIdx]) blobMaxX[blobIdx] = px;
        if (py < blobMinY[blobIdx]) blobMinY[blobIdx] = py;
        if (py > blobMaxY[blobIdx]) blobMaxY[blobIdx] = py;
      }
    }

    // Step 4: Extract and filter blobs
    const minArea = opts.minAreaPx ?? cfg.minAreaPx;
    const maxArea = opts.maxAreaPx ?? cfg.maxAreaPx;
    const maxBlobsCount = opts.maxBlobs ?? cfg.maxBlobs;

    const filteredBlobs = [];
    const denominatorStd = Math.max(bgStd, 1.0);

    for (let b = 0; b < numBlobs; b++) {
      const area = blobArea[b];
      if (area >= minArea && area <= maxArea) {
        const weight = blobSumWeight[b];
        const cx = weight > 0 ? blobSumX[b] / weight : (blobMinX[b] + blobMaxX[b]) / 2;
        const cy = weight > 0 ? blobSumY[b] / weight : (blobMinY[b] + blobMaxY[b]) / 2;
        const peak = blobPeak[b];
        const snr = (peak - bgMean) / denominatorStd;

        filteredBlobs.push({
          cx,
          cy,
          area,
          peak,
          snr,
          bbox: {
            x0: blobMinX[b],
            y0: blobMinY[b],
            x1: blobMaxX[b],
            y1: blobMaxY[b]
          }
        });
      }
    }

    // Sort blobs by peak score descending
    filteredBlobs.sort((a, b) => b.peak - a.peak);
    if (filteredBlobs.length > maxBlobsCount) {
      filteredBlobs.length = maxBlobsCount;
    }

    // Cleanup sparse lookups for next call
    for (let i = 0; i < numActive; i++) {
      const pIdx = sparseIndices[i];
      pixelToActiveIdx[pIdx] = -1;
      const root = find(i);
      blobRootToIdx[root] = -1;
    }

    const t1 = typeof performance !== 'undefined' ? performance.now() : Date.now();

    return {
      blobs: filteredBlobs,
      processingMs: t1 - t0
    };
  }

  return {
    detect
  };
}
