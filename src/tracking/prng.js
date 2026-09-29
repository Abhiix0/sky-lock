/**
 * Seeded Pseudo-Random Number Generator (PRNG) using Mulberry32 and Box-Muller transform.
 */

/**
 * Creates a 32-bit seeded uniform PRNG in [0, 1).
 *
 * @param {number} [seed=12345]
 * @returns {function(): number}
 */
export function createMulberry32(seed = 12345) {
  let a = (seed >>> 0) || 1;
  return function() {
    a |= 0;
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Creates a Gaussian (normal) random number generator.
 *
 * @param {function(): number} [rng] - Uniform PRNG function
 * @returns {function(number=, number=): number}
 */
export function createGaussian(rng = createMulberry32(12345)) {
  let spare = null;

  return function(mean = 0, std = 1) {
    if (spare !== null) {
      const val = spare;
      spare = null;
      return mean + val * std;
    }

    let u = 0;
    let v = 0;
    while (u === 0) u = rng();
    while (v === 0) v = rng();

    const mag = Math.sqrt(-2.0 * Math.log(u));
    const z0 = mag * Math.cos(2.0 * Math.PI * v);
    const z1 = mag * Math.sin(2.0 * Math.PI * v);

    spare = z1;
    return mean + z0 * std;
  };
}
