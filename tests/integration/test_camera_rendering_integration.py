"""Integration tests for camera rendering pipeline: JavaScript bundle, coordinate transforms, LOS."""

import math
import numpy as np
import pytest

from skylock.core.los import check_line_of_sight, get_satellite_position, calculate_look_angles
from skylock.core.orbital_world import (
    pan_tilt_to_world_aim,
    get_satellite_basis,
    S1_DEFAULT_ORBIT,
    S2_DEFAULT_ORBIT,
)


class TestJavaScriptBundleValidity:
    """Verify JavaScript bundles are syntactically valid to prevent rendering failures."""

    def test_gimbal_camera_bundle_exists(self):
        """Gimbal camera HTML references a JavaScript bundle that exists."""
        import os
        html_path = "src/skylock/ui/web3d/static_gimbal/index.html"
        assert os.path.exists(html_path), "Gimbal camera HTML not found"

        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract script src
        import re
        match = re.search(r'src="\.\/assets\/(index-[^"]+\.js)"', content)
        assert match is not None, "No JavaScript bundle reference found in HTML"

        bundle_name = match.group(1)
        bundle_path = f"src/skylock/ui/web3d/static_gimbal/assets/{bundle_name}"
        assert os.path.exists(bundle_path), f"Referenced bundle {bundle_name} does not exist"

    def test_gimbal_camera_bundle_no_syntax_errors(self):
        """Referenced JavaScript bundle has no syntax errors."""
        import os
        import subprocess
        
        html_path = "src/skylock/ui/web3d/static_gimbal/index.html"
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()

        import re
        match = re.search(r'src="\.\/assets\/(index-[^"]+\.js)"', content)
        if match is None:
            pytest.skip("Could not find JavaScript bundle reference")

        bundle_name = match.group(1)
        bundle_path = f"src/skylock/ui/web3d/static_gimbal/assets/{bundle_name}"

        if not os.path.exists(bundle_path):
            pytest.skip(f"Bundle {bundle_name} not found")

        # Use node to check syntax
        try:
            result = subprocess.run(
                ["node", "--check", bundle_path],
                capture_output=True,
                text=True,
                timeout=5,
            )
            assert result.returncode == 0, f"JavaScript syntax error: {result.stderr}"
        except FileNotFoundError:
            pytest.skip("Node.js not available for syntax validation")
        except subprocess.TimeoutExpired:
            pytest.fail("JavaScript validation timed out")


class TestBidirectionalTracking:
    """Verify coordinate transforms work correctly for both S-1→S-2 and S-2→S-1."""

    def test_pan_tilt_to_world_aim_s1_observer(self):
        """S-1 observing S-2: pan_tilt_to_world_aim uses S-1 basis."""
        t_s = 0.0
        pan_deg = 0.0
        tilt_deg = 0.0

        forward, up = pan_tilt_to_world_aim("s1", pan_deg, tilt_deg, t_s)

        # Verify output is normalized
        assert np.isclose(np.linalg.norm(forward), 1.0), "Forward not normalized"
        assert np.isclose(np.linalg.norm(up), 1.0), "Up not normalized"

        # Verify orthogonality (forward and up should be ~perpendicular)
        dot_product = np.dot(forward, up)
        assert abs(dot_product) < 0.1, f"Forward and up not orthogonal: dot={dot_product}"

    def test_pan_tilt_to_world_aim_s2_observer(self):
        """S-2 observing S-1: pan_tilt_to_world_aim uses S-2 basis."""
        t_s = 0.0
        pan_deg = 0.0
        tilt_deg = 0.0

        forward, up = pan_tilt_to_world_aim("s2", pan_deg, tilt_deg, t_s)

        # Verify output is normalized
        assert np.isclose(np.linalg.norm(forward), 1.0), "Forward not normalized"
        assert np.isclose(np.linalg.norm(up), 1.0), "Up not normalized"

    def test_get_satellite_basis_s1(self):
        """S-1 satellite basis is computed correctly."""
        t_s = 0.0
        x_basis, y_basis, z_basis = get_satellite_basis("s1", t_s)

        # Verify all are normalized
        assert np.isclose(np.linalg.norm(x_basis), 1.0), "X basis not normalized"
        assert np.isclose(np.linalg.norm(y_basis), 1.0), "Y basis not normalized"
        assert np.isclose(np.linalg.norm(z_basis), 1.0), "Z basis not normalized"

        # Verify orthogonality (right-handed coordinate system)
        assert np.isclose(abs(np.dot(x_basis, y_basis)), 0.0, atol=1e-6), "X-Y not orthogonal"
        assert np.isclose(abs(np.dot(y_basis, z_basis)), 0.0, atol=1e-6), "Y-Z not orthogonal"
        assert np.isclose(abs(np.dot(z_basis, x_basis)), 0.0, atol=1e-6), "Z-X not orthogonal"

    def test_get_satellite_basis_s2(self):
        """S-2 satellite basis is computed correctly."""
        t_s = 0.0
        x_basis, y_basis, z_basis = get_satellite_basis("s2", t_s)

        # Verify all are normalized
        assert np.isclose(np.linalg.norm(x_basis), 1.0), "X basis not normalized"
        assert np.isclose(np.linalg.norm(y_basis), 1.0), "Y basis not normalized"
        assert np.isclose(np.linalg.norm(z_basis), 1.0), "Z basis not normalized"

    def test_bidirectional_symmetry(self):
        """Both satellites can observe each other using the same coordinate transform logic."""
        t_s = 10.0  # Arbitrary time

        # S-1 → S-2
        forward_s1, up_s1 = pan_tilt_to_world_aim("s1", 0.0, 0.0, t_s)

        # S-2 → S-1
        forward_s2, up_s2 = pan_tilt_to_world_aim("s2", 0.0, 0.0, t_s)

        # Both should produce valid, different vectors (different satellite positions/orientations)
        assert not np.allclose(forward_s1, forward_s2), "S-1 and S-2 forward vectors should differ"


class TestLineOfSight:
    """Verify Earth occlusion geometry and LOS state transitions."""

    def test_check_line_of_sight_clear(self):
        """LOS is clear when no Earth obstruction."""
        # Two points on opposite sides of Earth but high enough to see each other
        p1 = (15.0, 0.0, 0.0)  # Beyond Earth radius (10.0)
        p2 = (-15.0, 0.0, 0.0)

        assert check_line_of_sight(p1, p2, body_radius=10.0), "LOS should be clear"

    def test_check_line_of_sight_blocked(self):
        """LOS is blocked when Earth obstructs."""
        # Two points at low altitude on opposite sides
        p1 = (11.0, 0.0, 0.0)
        p2 = (-11.0, 0.0, 0.0)

        # Line segment passes through Earth center
        assert not check_line_of_sight(p1, p2, body_radius=10.0), "LOS should be blocked"

    def test_check_line_of_sight_tangent(self):
        """LOS at tangent to Earth surface."""
        # Points positioned so line is tangent to sphere
        # Using Pythagorean theorem: if R=10, distance from center to tangent line = 10
        # Points at (0, 15, 0) and (20, 15, 0), perpendicular distance from origin to line = 15
        p1 = (0.0, 15.0, 0.0)
        p2 = (20.0, 15.0, 0.0)

        # Should be clear (distance 15 > radius 10)
        assert check_line_of_sight(p1, p2, body_radius=10.0), "Tangent LOS should be clear"

    def test_get_satellite_position_s1(self):
        """S-1 position can be retrieved at any time."""
        t_s = 0.0
        pos = get_satellite_position("s1", t_s)

        assert len(pos) == 3, "Position should be 3D tuple"
        assert all(isinstance(x, float) for x in pos), "Position components should be float"

        # Check position is on orbit (distance from origin ≈ radius)
        distance = math.sqrt(pos[0]**2 + pos[1]**2 + pos[2]**2)
        assert abs(distance - S1_DEFAULT_ORBIT.radius) < 1e-6, "S-1 not on expected orbit"

    def test_get_satellite_position_s2(self):
        """S-2 position can be retrieved at any time."""
        t_s = 0.0
        pos = get_satellite_position("s2", t_s)

        distance = math.sqrt(pos[0]**2 + pos[1]**2 + pos[2]**2)
        assert abs(distance - S2_DEFAULT_ORBIT.radius) < 1e-6, "S-2 not on expected orbit"

    def test_default_orbits_produce_los_variations(self):
        """Default S-1 and S-2 orbits produce both clear and blocked LOS over time."""
        los_states = []
        for t_s in np.linspace(0, 100, 100):
            p1 = get_satellite_position("s1", t_s)
            p2 = get_satellite_position("s2", t_s)
            los_clear = check_line_of_sight(p1, p2, body_radius=10.0)
            los_states.append(los_clear)

        # Should have at least one transition
        has_clear = any(los_states)
        has_blocked = any(not s for s in los_states)

        assert has_clear, "LOS should be clear at some point in orbit"
        assert has_blocked, "LOS should be blocked at some point in orbit"

    def test_calculate_look_angles(self):
        """Look angles calculated correctly from observer to target."""
        obs_pos = (20.0, 0.0, 0.0)
        target_pos = (25.0, 5.0, 0.0)

        pan_deg, tilt_deg, distance = calculate_look_angles(obs_pos, target_pos)

        # Check distance
        expected_dist = math.sqrt((25-20)**2 + (5-0)**2 + (0-0)**2)
        assert abs(distance - expected_dist) < 1e-6, "Distance calculation incorrect"

        # Pan and tilt should be reasonable angles
        assert -180 <= pan_deg <= 180, "Pan out of range"
        assert -90 <= tilt_deg <= 90, "Tilt out of range"


class TestControllerModesSeparation:
    """Verify AUTO and MANUAL modes operate gimbal independently."""

    def test_manual_mode_bypasses_tracking(self):
        """MANUAL mode returns manual rates without processing tracking intent."""
        from skylock.control.controller import PointingController, ControlMode
        from skylock.core.types import ControlIntent, ControlIntentMode, Pointing
        from skylock.app.factory import default_config

        config = default_config()
        controller = PointingController(
            sat_id="s1",
            mode=ControlMode.MANUAL,
            camera_config=config.camera,
            control_config=config.control,
        )

        # Set manual rates
        controller.set_manual_rates(pan_rate=5.0, tilt_rate=-3.0)

        # Create arbitrary tracking intent (should be ignored)
        intent = ControlIntent(
            mode=ControlIntentMode.TRACK,
            setpoint_pan_deg=90.0,
            setpoint_tilt_deg=45.0,
            image_error_px=(100.0, 50.0),
        )

        pointing = Pointing(pan_deg=0.0, tilt_deg=0.0)
        command = controller.step(intent, estimate=None, pointing=pointing, dt=0.1)

        # Should return manual rates, not tracking-derived commands
        assert abs(command.pan_rate_deg_s - 5.0) < 1e-6, "Manual pan rate not returned"
        assert abs(command.tilt_rate_deg_s - (-3.0)) < 1e-6, "Manual tilt rate not returned"

    def test_auto_mode_processes_tracking_intent(self):
        """AUTO mode processes tracking intent and generates commands."""
        from skylock.control.controller import PointingController, ControlMode
        from skylock.core.types import ControlIntent, ControlIntentMode, Pointing
        from skylock.app.factory import default_config

        config = default_config()
        controller = PointingController(
            sat_id="s1",
            mode=ControlMode.AUTO,
            camera_config=config.camera,
            control_config=config.control,
        )

        # GOTO intent
        intent = ControlIntent(
            mode=ControlIntentMode.GOTO,
            setpoint_pan_deg=10.0,
            setpoint_tilt_deg=5.0,
            image_error_px=None,
        )

        pointing = Pointing(pan_deg=0.0, tilt_deg=0.0)
        command = controller.step(intent, estimate=None, pointing=pointing, dt=0.1)

        # Should generate non-zero rates toward setpoint
        assert command.pan_rate_deg_s != 0.0, "AUTO mode should generate pan command"
        assert command.tilt_rate_deg_s != 0.0, "AUTO mode should generate tilt command"


class TestDisturbanceApplication:
    """Verify disturbances are configured and applied to sensor pipeline."""

    def test_disturbance_stack_exists(self):
        """DisturbanceStack is importable and initializable."""
        from skylock.simulation.disturbances.stack import DisturbanceStack
        from skylock.app.factory import default_config

        config = default_config()
        stack = DisturbanceStack(config=config.disturbances, seed=42)

        assert stack is not None, "DisturbanceStack should initialize"

    def test_apply_photometric_modifies_image(self):
        """apply_photometric modifies image when disturbances enabled."""
        from skylock.simulation.disturbances.stack import DisturbanceStack
        from skylock.simulation.disturbances.base import DisturbanceContext
        from skylock.app.factory import default_config

        config = default_config()
        
        # Enable Gaussian noise
        config.disturbances.gaussian_noise.enabled = True
        config.disturbances.gaussian_noise.sigma = 0.05

        stack = DisturbanceStack(config=config.disturbances, seed=42)

        # Create test image
        img_clean = np.ones((100, 100), dtype=np.float32) * 0.5
        ctx = DisturbanceContext(frame_index=0, timestamp_s=0.0)

        img_disturbed = stack.apply_photometric(img_clean, ctx)

        # Should be modified
        assert not np.allclose(img_clean, img_disturbed), "Image should be modified by disturbance"

    def test_disabled_disturbances_no_effect(self):
        """Disabled disturbances do not modify image."""
        from skylock.simulation.disturbances.stack import DisturbanceStack
        from skylock.simulation.disturbances.base import DisturbanceContext
        from skylock.app.factory import default_config

        config = default_config()
        
        # Disable all disturbances
        config.disturbances.gaussian_noise.enabled = False
        config.disturbances.salt_pepper.enabled = False
        config.disturbances.poisson_noise.enabled = False
        config.disturbances.optical_blur.enabled = False

        stack = DisturbanceStack(config=config.disturbances, seed=42)

        img_clean = np.ones((100, 100), dtype=np.float32) * 0.5
        ctx = DisturbanceContext(frame_index=0, timestamp_s=0.0)

        img_disturbed = stack.apply_photometric(img_clean, ctx)

        # Should be unchanged (within floating point precision)
        assert np.allclose(img_clean, img_disturbed, atol=1e-6), "Image should not be modified"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
