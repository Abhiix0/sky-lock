/**
 * Tracking API: Public boundary interface for autonomous tracking algorithms.
 *
 * All Phase 2+ algorithms (detector, Kalman filter, PID controller, state machine)
 * interact with the simulation, virtual camera, and gimbal strictly through this API.
 */

/**
 * @typedef {Object} FeedFrame
 * @property {number} width - Frame width in pixels
 * @property {number} height - Frame height in pixels
 * @property {Uint8Array} data - RGBA pixel buffer (bottom-up from WebGL)
 * @property {number} timestamp - Simulation timestamp in seconds
 * @property {number} frameId - Monotonically increasing frame sequence ID
 */

/**
 * @typedef {Object} GimbalState
 * @property {number} panDeg - Current pan angle in degrees (-180, 180]
 * @property {number} tiltDeg - Current tilt angle in degrees [-90, 90]
 * @property {number} panRateDegS - Current pan angular rate in deg/s
 * @property {number} tiltRateDegS - Current tilt angular rate in deg/s
 * @property {string} mode - Active gimbal servo mode ('GOTO' | 'RATE')
 * @property {boolean} atLimitPan - Whether pan is clamped at hard mechanical limit
 * @property {boolean} atLimitTilt - Whether tilt is clamped at hard mechanical limit
 */

/**
 * @typedef {Object} GroundTruth
 * @property {number} panDeg - True line-of-sight pan angle from observer body frame
 * @property {number} tiltDeg - True line-of-sight tilt angle from observer body frame
 * @property {number} pixelX - True target projection X coordinate in feed pixels
 * @property {number} pixelY - True target projection Y coordinate in feed pixels
 * @property {boolean} inFrustum - Whether the target is within the camera field of view
 */

/**
 * @typedef {Object} TrackingApi
 * @property {function(): FeedFrame} getFrame - Returns latest camera feed frame
 * @property {function(number, number): void} setGimbalCommand - Commands gimbal to target angles (pan, tilt) in deg
 * @property {function(number, number): void} setGimbalRateCommand - Commands gimbal angular rates (panRate, tiltRate) in deg/s
 * @property {function(): GimbalState} getGimbalState - Returns current gimbal telemetry
 * @property {function(): GroundTruth} getGroundTruth - Returns true target line-of-sight and projection
 * @property {function(): number} getSimTime - Returns current simulation time in seconds
 */

/**
 * Creates the Tracking API boundary.
 *
 * @param {Object} options
 * @param {Object} options.virtualCamera - Virtual camera instance
 * @param {Object} options.gimbal - Gimbal servo instance
 * @param {Object} options.simClock - Simulation clock instance
 * @param {function(): Object|null} options.getTargetSat - Function returning active target satellite
 * @returns {TrackingApi}
 */
export function createTrackingApi({ virtualCamera, gimbal, simClock, getTargetSat }) {
  return {
    /**
     * Get the latest rendered camera feed frame.
     * @returns {FeedFrame}
     */
    getFrame() {
      return virtualCamera.getFrame();
    },

    /**
     * Set target gimbal pan and tilt angle setpoint.
     * @param {number} panDeg
     * @param {number} tiltDeg
     */
    setGimbalCommand(panDeg, tiltDeg) {
      gimbal.setGimbalCommand(panDeg, tiltDeg);
    },

    /**
     * Set target gimbal angular rates.
     * @param {number} panRateDegS
     * @param {number} tiltRateDegS
     */
    setGimbalRateCommand(panRateDegS, tiltRateDegS) {
      gimbal.setGimbalRateCommand(panRateDegS, tiltRateDegS);
    },

    /**
     * Get current gimbal telemetry and mechanical status.
     * @returns {GimbalState}
     */
    getGimbalState() {
      return gimbal.getGimbalState();
    },

    /**
     * Get ground-truth geometric relationship to target satellite.
     * @returns {GroundTruth}
     */
    getGroundTruth() {
      const target = getTargetSat ? getTargetSat() : null;
      return virtualCamera.getGroundTruthDirection(target);
    },

    /**
     * Get current simulation time in seconds.
     * @returns {number}
     */
    getSimTime() {
      return simClock.getSimTime();
    }
  };
}
