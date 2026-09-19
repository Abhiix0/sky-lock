import * as THREE from 'three';

/**
 * Inter-Satellite Comms Console
 * Generates terminal-style telemetry logs built from live satellite orbit positions.
 */

let logContainer = null;
let statusDot = null;
let lastLogTime = 0;
let tickCount = 0;

// Earth radius conversion (1 Three.js unit ≈ 637.1 km)
const KM_PER_UNIT = 637.1;
const SPEED_OF_LIGHT_KMS = 299792;

// Reusable math objects to prevent per-frame garbage collection
const _posA = new THREE.Vector3();
const _posB = new THREE.Vector3();
const _tanA = new THREE.Vector3();
const _tanB = new THREE.Vector3();
const _velA = new THREE.Vector3();
const _velB = new THREE.Vector3();
const _deltaV = new THREE.Vector3();

/**
 * Format current local time as [HH:MM:SS]
 */
function getTimeString() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
}

/**
 * Append a formatted line to the terminal log with auto-scroll and cap.
 */
function appendLog(html) {
  if (!logContainer) return;

  const line = document.createElement('div');
  line.className = 'comms-line';
  line.innerHTML = html;
  logContainer.appendChild(line);

  // Cap at ~50 lines to prevent DOM bloat
  while (logContainer.children.length > 50) {
    logContainer.removeChild(logContainer.firstChild);
  }

  // Smoothly auto-scroll to latest message
  logContainer.scrollTop = logContainer.scrollHeight;
}

/**
 * Initialize the comms console DOM connections and starting logs.
 */
export function initCommsConsole() {
  logContainer = document.getElementById('comms-log-container');
  statusDot = document.getElementById('comms-status-dot');

  if (!logContainer) return;

  appendLog(
    `[${getTimeString()}] <span class="comms-peer">SYSTEM</span> | <span class="comms-type">[INIT]</span> | ISL terminal initialized | Ka-band 23.4 GHz`
  );
  appendLog(
    `[${getTimeString()}] <span class="comms-peer">SYSTEM</span> | <span class="comms-type">[ACQUIRE]</span> | tracking crosslink telemetry...`
  );
}

/**
 * Update comms console telemetry logs called from main animation loop.
 * Triggers a new telemetry entry every ~1.2 to 1.5 seconds.
 *
 * @param {Array<Object>} activeSatellites
 */
export function update(activeSatellites) {
  if (!logContainer) {
    logContainer = document.getElementById('comms-log-container');
    statusDot = document.getElementById('comms-status-dot');
    if (!logContainer) return;
  }

  const currentTime = performance.now();

  // Trigger roughly every 1.35 seconds
  if (currentTime - lastLogTime < 1350) {
    return;
  }
  lastLogTime = currentTime;
  tickCount++;

  const timeStr = getTimeString();

  // Filter operational satellites
  const operational = (activeSatellites || []).filter(
    (s) => s && s.model && !s.paused && s.model.visible !== false
  );
  const totalInMode = (activeSatellites || []).filter(
    (s) => s && s.model && s.model.visible !== false
  );

  // Update status indicator dot
  if (statusDot) {
    if (operational.length >= 2) {
      statusDot.classList.remove('offline');
    } else {
      statusDot.classList.add('offline');
    }
  }

  // Case 1: 2+ active satellites connected
  if (operational.length >= 2) {
    const satA = operational[0];
    const satB = operational[1];

    satA.model.getWorldPosition(_posA);
    satB.model.getWorldPosition(_posB);

    // Compute real distance in km
    const distUnits = _posA.distanceTo(_posB);
    const distKm = Math.round(distUnits * KM_PER_UNIT);

    // Compute relative velocity (Δv) from orbital mechanics
    let dv = 3.2;
    if (satA.orbit && satB.orbit && typeof satA.orbit.getTangent === 'function' && typeof satB.orbit.getTangent === 'function') {
      satA.orbit.getTangent(_tanA);
      satB.orbit.getTangent(_tanB);

      const rA = Math.max(10, _posA.length()) * KM_PER_UNIT;
      const rB = Math.max(10, _posB.length()) * KM_PER_UNIT;

      // Standard orbital speed v = sqrt(GM / r) with Earth GM = 398600 km^3/s^2
      const speedA = Math.sqrt(398600 / rA) * (satA.individualSpeed || 1);
      const speedB = Math.sqrt(398600 / rB) * (satB.individualSpeed || 1);

      _velA.copy(_tanA).multiplyScalar(speedA);
      _velB.copy(_tanB).multiplyScalar(speedB);
      _deltaV.subVectors(_velA, _velB);
      dv = _deltaV.length();
    }

    const dvStr = (dv > 0 ? dv : 3.2).toFixed(1);
    const direction = (tickCount % 2 === 0)
      ? `${satA.id} -> ${satB.id}`
      : `${satB.id} -> ${satA.id}`;

    // Rotate across 4 standard protocol message types
    const messageTypes = ['POSITION_SYNC', 'RANGING', 'HANDSHAKE', 'DATA_PACKET'];
    const currentType = messageTypes[tickCount % messageTypes.length];

    let logHtml = '';

    switch (currentType) {
      case 'POSITION_SYNC': {
        const senderPos = (tickCount % 2 === 0) ? _posA : _posB;
        const x = Math.round(senderPos.x * KM_PER_UNIT);
        const y = Math.round(senderPos.y * KM_PER_UNIT);
        const z = Math.round(senderPos.z * KM_PER_UNIT);
        logHtml = `[${timeStr}] <span class="comms-peer">${direction}</span> | <span class="comms-type">[POSITION_SYNC]</span> | dist: <span class="comms-dist">${distKm.toLocaleString()} km</span> | Δv: <span class="comms-dv">${dvStr} km/s</span> | link: <span class="comms-link-locked">LOCKED</span> | eph: [${x}, ${y}, ${z}] sync OK`;
        break;
      }

      case 'RANGING': {
        const tofMs = ((distKm / SPEED_OF_LIGHT_KMS) * 1000).toFixed(1);
        logHtml = `[${timeStr}] <span class="comms-peer">${direction}</span> | <span class="comms-type">[RANGING]</span> | dist: <span class="comms-dist">${distKm.toLocaleString()} km</span> | Δv: <span class="comms-dv">${dvStr} km/s</span> | link: <span class="comms-link-locked">LOCKED</span> | tof: ${tofMs} ms`;
        break;
      }

      case 'HANDSHAKE': {
        const freqs = ['23.4 GHz', '23.8 GHz', '24.1 GHz', '24.5 GHz'];
        const freq = freqs[tickCount % freqs.length];
        logHtml = `[${timeStr}] <span class="comms-peer">${direction}</span> | <span class="comms-type">[HANDSHAKE]</span> | dist: <span class="comms-dist">${distKm.toLocaleString()} km</span> | Δv: <span class="comms-dv">${dvStr} km/s</span> | link: <span class="comms-link-locked">LOCKED</span> | carrier: ${freq} SYNC`;
        break;
      }

      case 'DATA_PACKET':
      default: {
        const packetSizes = ['256kb', '512kb', '1024kb', '128kb'];
        const packet = packetSizes[tickCount % packetSizes.length];
        logHtml = `[${timeStr}] <span class="comms-peer">${direction}</span> | <span class="comms-type">[DATA_PACKET]</span> | dist: <span class="comms-dist">${distKm.toLocaleString()} km</span> | Δv: <span class="comms-dv">${dvStr} km/s</span> | link: <span class="comms-link-locked">LOCKED</span> | packet: ${packet} sent`;
        break;
      }
    }

    appendLog(logHtml);
    return;
  }

  // Case 2: Satellites exist in mode, but one/both are paused
  if (totalInMode.length >= 2) {
    const pausedSat = totalInMode.find((s) => s.paused);
    const pausedId = pausedSat ? pausedSat.id : 'PEER';
    appendLog(
      `[${timeStr}] <span class="comms-peer">ISL-MONITOR</span> | <span class="comms-type">[LINK_HOLD]</span> | link: <span class="comms-link-wait">HOLD (${pausedId} PAUSED)</span> | carrier standby`
    );
    return;
  }

  // Case 3: Only 1 satellite deployed
  if (totalInMode.length === 1) {
    appendLog(
      `[${timeStr}] <span class="comms-peer">${totalInMode[0].id}</span> | <span class="comms-type">[RANGING]</span> | link: <span class="comms-link-wait">SEARCHING</span> | awaiting peer satellite`
    );
    return;
  }

  // Case 4: No satellites in current mode
  appendLog(
    `[${timeStr}] <span class="comms-peer">ISL-CORE</span> | <span class="comms-type">[STANDBY]</span> | link: <span class="comms-link-wait">IDLE</span> | no active satellites`
  );
}
