import math

import pytest

from marineprop import (
    OperatingPoint, calculate, coefficients_from_measurement,
    interpolate_coefficients,
)


def test_known_point():
    point = OperatingPoint(0.06, 3000, 1.5, 998.0)
    result = calculate(point, 0.12, 0.025)
    assert result.advance_coefficient == pytest.approx(0.5)
    assert result.thrust_n == pytest.approx(3.880224)
    assert result.torque_nm == pytest.approx(0.0485028)
    assert result.shaft_power_w == pytest.approx(2 * math.pi * 50 * result.torque_nm)
    assert result.efficiency == pytest.approx(0.5 * 0.12 / (2 * math.pi * 0.025))


def test_measurement_roundtrip():
    point = OperatingPoint(0.08, 2400, 0.8)
    result = calculate(point, 0.15, 0.03)
    kt, kq = coefficients_from_measurement(point, result.thrust_n, result.torque_nm)
    assert (kt, kq) == pytest.approx((0.15, 0.03))


def test_interpolation_and_no_extrapolation():
    x, kt, kq = [0, 0.4, 0.8], [0.2, 0.15, 0.1], [0.03, 0.025, 0.02]
    assert interpolate_coefficients(x, kt, kq, 0.2) == pytest.approx((0.175, 0.0275))
    with pytest.raises(ValueError):
        interpolate_coefficients(x, kt, kq, 0.9)


def test_zero_rpm():
    point = OperatingPoint(0.06, 0, 1.0)
    result = calculate(point, 0.1, 0.02)
    assert result.advance_coefficient is None
    assert result.thrust_n == 0
    assert result.efficiency is None
    with pytest.raises(ValueError):
        coefficients_from_measurement(point, 1, 0.01)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        OperatingPoint(-1, 1000, 1)
    with pytest.raises(ValueError):
        calculate(OperatingPoint(0.06, 3000, 1), float("nan"), 0.02)
    with pytest.raises(ValueError):
        interpolate_coefficients([0.1, 0.1], [0.2, 0.3], [0.01, 0.02], 0.1)
