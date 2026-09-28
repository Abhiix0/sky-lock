# Sky Lock - Space Environment Simulation

A Three.js-based space environment prototype featuring Earth and orbiting satellites. Built for hackathon demo purposes with clean visuals and easily tweakable parameters.

## Features

- **Pure black space background** (skybox to be added in future phase)
- **Normalized 3D models** - Earth and satellites auto-scaled from GLB files
- **Dual satellite orbits** - Two satellites on different orbital planes
- **Orbit visualization** - Subtle path lines showing orbital planes
- **Interactive camera** - Orbit controls with zoom and rotation
- **Performance monitoring** - Built-in FPS counter
- **Triangle count logging** - Asset complexity reporting

## Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

The application will automatically open in your browser at `http://localhost:3000`.

## Project Structure

```
sky-lock/
├── public/
│   └── assets/
│       ├── earth.glb               # Earth 3D model
│       ├── satellite.glb           # Satellite 1 3D model
│       ├── satellite2.glb          # Satellite 2 3D model
│       └── skybox.glb (not yet present - reserved for future phase)
├── src/
│   ├── GLTFSpecGlossExtension.js   # KHR_materials_pbrSpecularGlossiness support
│   ├── loadAssets.js               # GLB loading & normalization
│   ├── main.js                     # Application entry & animation loop
│   ├── orbit.js                    # Orbit calculations & visualization
│   ├── sceneSetup.js               # Scene, camera, renderer, lighting
│   └── ui.js                       # UI control panel, state management & preview
├── index.html
├── package.json
└── vite.config.js
```

## Configuration

All major parameters are exposed as constants at the top of each file for easy tweaking:

### Model Scales (`src/loadAssets.js`)
```javascript
export const EARTH_RADIUS = 10;
export const SATELLITE_SIZE = 2.0;
```

### Orbit Parameters (`src/orbit.js`)
```javascript
// Automatic orbit parameters
export const ORBIT_1_RADIUS      = 20;    // 2× Earth radius
export const ORBIT_1_SPEED       = 0.3;   // radians per second
export const ORBIT_1_INCLINATION = 25;    // degrees

export const ORBIT_2_RADIUS      = 26;    // 2.6× Earth radius
export const ORBIT_2_SPEED       = 0.2;   // radians per second
export const ORBIT_2_INCLINATION = 65;    // degrees

// Manual orbit constraints
export const MAX_MANUAL_SATELLITES     = 2;
export const MANUAL_ORBIT_ECCENTRICITY = 0.25;
export const MIN_SATELLITE_DISTANCE    = EARTH_RADIUS * 1.15; // 11.5
export const MAX_SATELLITE_DISTANCE    = 38.0;
```

### Camera & Lighting (`src/sceneSetup.js`)
```javascript
export const CAMERA_FOV  = 60;
export const CAMERA_NEAR = 0.1;
export const CAMERA_FAR  = 10000;
export const CAMERA_INITIAL_POSITION = { x: 32, y: 24, z: 38 };

export const SUN_INTENSITY    = 3.0;
export const SUN_POSITION     = { x: 20, y: 10, z: 15 };
export const AMBIENT_INTENSITY = 0.15;
```

## Asset Pipeline

The project includes automatic model normalization:

1. **Bounding box calculation** - Computes true model dimensions
2. **Re-centering** - Centers model on its own origin
3. **Normalization** - Scales to target size regardless of source scale
4. **Triangle counting** - Logs complexity for optimization decisions

This ensures models from different creators work together seamlessly.

## Controls

- **Left mouse drag** - Rotate camera around Earth
- **Scroll wheel** - Zoom in/out
- **Panning disabled** - Keeps Earth centered

## Performance

- Target: 60 FPS
- Shadows enabled (can be disabled in `sceneSetup.js` if needed)
- Single satellite model reused via cloning
- Efficient orbit calculation using parametric motion

## Future Phases

- [ ] Add skybox.glb for space background
- [ ] Add star field
- [ ] Additional satellites
- [ ] Orbital decay simulation
- [ ] Ground station markers

## Technical Notes

- Uses Three.js color space and tone mapping for proper glTF rendering
- Orbit lines use low-poly line loops for minimal performance impact
- Satellites oriented toward Earth for natural appearance
- Models are never clipped into Earth (orbit radii > Earth radius)

## Browser Compatibility

Requires modern browser with WebGL 2.0 support:
- Chrome 79+
- Firefox 71+
- Safari 14+
- Edge 79+
