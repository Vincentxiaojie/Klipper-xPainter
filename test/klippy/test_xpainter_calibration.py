# Unit tests for xPainter calibration math formulas
#
# These tests validate the core calibration calculations
# without requiring a running Klipper instance.
#
# Usage: PYTHONPATH=klipper pytest test/klippy/test_xpainter_calibration.py -v

import math
import pytest


# ============================================================
# Calibration formulas (mirrors xpainter_calibration.py)
# ============================================================

def compute_tool_length(L_current, dx, B_angle):
    """Calculate corrected tool_length from X deviation.

    L_new = L_current + dx / sin(B_angle)

    Args:
        L_current: Current tool_length (mm)
        dx: X deviation between B=0 and B=θ dots (x2 - x1, mm)
        B_angle: B axis angle used for dot 2 (degrees)

    Returns:
        Corrected tool_length (mm)
    """
    sin_b = math.sin(math.radians(B_angle))
    if abs(sin_b) < 1e-10:
        raise ValueError("B_angle too small, sin(B) ≈ 0")
    return L_current + dx / sin_b


def compute_pivot_offset(dx, C_angle):
    """Calculate pivot_y offset from X deviation.

    offset = -dx / sin(C_angle)

    Args:
        dx: X deviation between C=0 and C=θ dots (x2 - x1, mm)
        C_angle: C axis angle used for dot 2 (degrees)

    Returns:
        Corrected pivot_y offset (mm)
    """
    sin_c = math.sin(math.radians(C_angle))
    if abs(sin_c) < 1e-10:
        raise ValueError("C_angle too small, sin(C) ≈ 0")
    return -dx / sin_c


def simulate_tool_deviation(L_true, L_used, B_angle):
    """Simulate the X deviation that would be observed when tool_length is wrong.

    If the actual tool_length is L_true but the system uses L_used,
    the RTCP transform will mis-compensate by:
        dx = (L_true - L_used) * sin(B_angle)

    This is the expected dot displacement when marking at B=θ vs B=0.
    """
    return (L_true - L_used) * math.sin(math.radians(B_angle))


# ============================================================
# Test cases
# ============================================================

class TestToolLengthFormula:
    """Tests for compute_tool_length()."""

    def test_basic_correction_positive(self):
        """B=30°, sin(30°)=0.5, dx=5 → ΔL=10, L_new=60"""
        result = compute_tool_length(50, 5, 30)
        assert result == pytest.approx(60.0, abs=0.001)

    def test_basic_correction_negative(self):
        """Negative dx means tool_length too long"""
        result = compute_tool_length(60, -5, 30)
        assert result == pytest.approx(50.0, abs=0.001)

    def test_zero_deviation(self):
        """Zero deviation means tool_length is already correct"""
        result = compute_tool_length(48.8, 0, 30)
        assert result == pytest.approx(48.8, abs=0.001)

    def test_B15_angle(self):
        """B=15°, sin(15°)=0.258819, dx=3 → ΔL≈11.59"""
        result = compute_tool_length(80, 3, 15)
        expected = 80 + 3 / 0.258819045
        assert result == pytest.approx(expected, abs=0.01)

    def test_B20_angle(self):
        """B=20°, sin(20°)=0.342020"""
        result = compute_tool_length(50, 10, 20)
        expected = 50 + 10 / 0.342020143
        assert result == pytest.approx(expected, abs=0.01)

    def test_large_deviation(self):
        """Large deviation, B=45°, sin(45°)=0.707107"""
        result = compute_tool_length(100, 20, 45)
        expected = 100 + 20 / 0.707106781
        assert result == pytest.approx(expected, abs=0.01)

    def test_very_small_angle_raises(self):
        """Nearly zero angle should raise ValueError"""
        with pytest.raises(ValueError):
            compute_tool_length(50, 5, 0)

    def test_roundtrip_perfect_tool_length(self):
        """Roundtrip: given true L, simulate deviation, compute correction.
        Should recover exact L_true."""
        L_true = 55.0
        L_used = 50.0  # wrong tool_length
        B_angle = 30.0

        dx = simulate_tool_deviation(L_true, L_used, B_angle)
        # dx should be (55-50)*0.5 = 2.5
        assert dx == pytest.approx(2.5, abs=0.001)

        # Correct back
        L_corrected = compute_tool_length(L_used, dx, B_angle)
        assert L_corrected == pytest.approx(L_true, abs=0.001)

    def test_roundtrip_various(self):
        """Roundtrip test for various parameter combinations."""
        test_cases = [
            (55.0, 50.0, 30.0),
            (80.0, 90.0, 20.0),
            (48.8, 40.0, 15.0),
            (100.0, 95.0, 30.0),
            (65.0, 70.0, 25.0),
        ]
        for L_true, L_used, B_angle in test_cases:
            dx = simulate_tool_deviation(L_true, L_used, B_angle)
            L_corrected = compute_tool_length(L_used, dx, B_angle)
            assert L_corrected == pytest.approx(L_true, abs=0.001), \
                f"Roundtrip failed: L_true={L_true}, L_used={L_used}, B={B_angle}"

    def test_roundtrip_negative_angle(self):
        """Roundtrip with negative B angle."""
        L_true = 55.0
        L_used = 50.0
        B_angle = -30.0

        dx = simulate_tool_deviation(L_true, L_used, B_angle)
        L_corrected = compute_tool_length(L_used, dx, B_angle)
        assert L_corrected == pytest.approx(L_true, abs=0.001)


class TestPivotOffsetFormula:
    """Tests for compute_pivot_offset()."""

    def test_basic_negative_dx(self):
        """C=30°, dx=-5 → offset = -(-5)/0.5 = 10"""
        result = compute_pivot_offset(-5, 30)
        assert result == pytest.approx(10.0, abs=0.001)

    def test_basic_positive_dx(self):
        """C=30°, dx=5 → offset = -(5)/0.5 = -10"""
        result = compute_pivot_offset(5, 30)
        assert result == pytest.approx(-10.0, abs=0.001)

    def test_zero_deviation(self):
        """Zero deviation → offset=0"""
        result = compute_pivot_offset(0, 30)
        assert result == pytest.approx(0.0, abs=0.001)

    def test_C20_angle(self):
        """C=20°, sin(20°)=0.342020"""
        result = compute_pivot_offset(-3, 20)
        expected = -(-3) / 0.342020143
        assert result == pytest.approx(expected, abs=0.01)


class TestSimulateToolDeviation:
    """Tests for simulate_tool_deviation()."""

    def test_L_used_too_small(self):
        """L_used < L_true → positive dx (dot 2 to the right of dot 1)"""
        dx = simulate_tool_deviation(55, 50, 30)
        assert dx > 0
        assert dx == pytest.approx(2.5, abs=0.001)

    def test_L_used_too_large(self):
        """L_used > L_true → negative dx (dot 2 to the left of dot 1)"""
        dx = simulate_tool_deviation(50, 55, 30)
        assert dx < 0
        assert dx == pytest.approx(-2.5, abs=0.001)

    def test_perfect_match(self):
        """Matching L → zero deviation"""
        dx = simulate_tool_deviation(50, 50, 30)
        assert dx == pytest.approx(0.0, abs=0.001)


class TestBrushDirectionLogic:
    """Tests for brush direction constraint logic."""

    def direction_is_safe(self, B_angle, dx_sign):
        """Return True if movement direction is safe for given B angle.

        B>0 (pen tip right): safe if dx_sign < 0 (moving left)
        B=0 (vertical): always safe
        B<0 (pen tip left): safe if dx_sign > 0 (moving right)
        """
        if B_angle == 0:
            return True
        elif B_angle > 0:
            return dx_sign < 0
        else:
            return dx_sign > 0

    def test_B_positive_must_move_left(self):
        """B>0: only leftward (negative X) movement is safe."""
        assert self.direction_is_safe(15, -1) == True   # move left, safe
        assert self.direction_is_safe(15, 1) == False   # move right, unsafe
        assert self.direction_is_safe(30, -1) == True

    def test_B_zero_any_direction(self):
        """B=0: any direction is safe."""
        assert self.direction_is_safe(0, -1) == True
        assert self.direction_is_safe(0, 1) == True

    def test_B_negative_must_move_right(self):
        """B<0: only rightward (positive X) movement is safe."""
        assert self.direction_is_safe(-15, 1) == True    # move right, safe
        assert self.direction_is_safe(-15, -1) == False  # move left, unsafe
        assert self.direction_is_safe(-30, 1) == True
