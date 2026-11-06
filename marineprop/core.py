"""MarineProp Studio computational core. SI units throughout."""
from __future__ import annotations

from dataclasses import dataclass
from math import pi, isfinite, hypot
from typing import Iterable

import numpy as np


def finite_value(value: float) -> float:
    if not isfinite(value):
        raise ValueError("Numerical range exceeded; check input magnitudes.")
    return value


def dimensional_scales(point):
    if point.revolutions_per_second == 0:
        return 0.0, 0.0
    try:
        t = point.density_kg_m3 * point.revolutions_per_second**2 * point.diameter_m**4
        q = t * point.diameter_m
        if t == 0 or q == 0:
            raise ValueError("Dimensional scale underflow; check input magnitudes.")
        return finite_value(t), finite_value(q)
    except OverflowError as exc:
        raise ValueError("Numerical range exceeded; check input magnitudes.") from exc


@dataclass(frozen=True)
class OperatingPoint:
    diameter_m: float
    rpm: float
    advance_speed_m_s: float
    density_kg_m3: float = 998.2
    kinematic_viscosity_m2_s: float = 1.004e-6

    def __post_init__(self) -> None:
        for field in ("diameter_m", "rpm", "advance_speed_m_s", "density_kg_m3", "kinematic_viscosity_m2_s"):
            value = getattr(self, field)
            if not isfinite(value):
                raise ValueError(f"{field} must be finite")
        if self.diameter_m <= 0 or self.density_kg_m3 <= 0 or self.kinematic_viscosity_m2_s <= 0:
            raise ValueError("Diameter, density and kinematic viscosity must be positive.")
        if self.rpm < 0 or self.advance_speed_m_s < 0:
            raise ValueError("RPM and advance speed must be nonnegative.")

    @property
    def rotational_reynolds_number(self) -> float:
        """Re_n = n D² / nu; not a blade-section Reynolds number."""
        try:
            return finite_value(self.revolutions_per_second * self.diameter_m**2 / self.kinematic_viscosity_m2_s)
        except OverflowError as exc:
            raise ValueError("Reynolds numerical range exceeded.") from exc

    def blade_reynolds_number(self, chord_07r_m: float) -> float:
        """Section Re at 0.7R, using geometric relative speed, no induction."""
        if not isfinite(chord_07r_m) or chord_07r_m <= 0:
            raise ValueError("Section chord must be finite and positive.")
        speed = hypot(self.advance_speed_m_s,
                         0.7 * pi * self.revolutions_per_second * self.diameter_m)
        return finite_value(speed * chord_07r_m / self.kinematic_viscosity_m2_s)

    @property
    def revolutions_per_second(self) -> float:
        return self.rpm / 60.0

    @property
    def advance_coefficient(self) -> float | None:
        n = self.revolutions_per_second
        if n == 0:
            return None
        denominator = finite_value(n * self.diameter_m)
        if denominator == 0:
            raise ValueError("Advance denominator underflow.")
        return finite_value(self.advance_speed_m_s / denominator)


@dataclass(frozen=True)
class Performance:
    advance_coefficient: float | None
    kt: float
    kq: float
    thrust_n: float
    torque_nm: float
    shaft_power_w: float
    efficiency: float | None


def calculate(point: OperatingPoint, kt: float, kq: float) -> Performance:
    """Evaluate open-water definitions for supplied KT and KQ.

    Coefficients must be obtained from a documented propeller model or test.
    No geometry-to-coefficient prediction is implied.
    """
    if not all(isfinite(x) for x in (kt, kq)):
        raise ValueError("KT and KQ must be finite.")
    n = point.revolutions_per_second
    j = point.advance_coefficient
    t_scale, q_scale = dimensional_scales(point)
    thrust = finite_value(kt * t_scale)
    torque = finite_value(kq * q_scale)
    shaft_power = finite_value(2 * pi * n * torque)
    efficiency = None
    if j is not None and kq > 0 and kt >= 0:
        efficiency = finite_value(j * kt / finite_value(2 * pi * kq))
    return Performance(j, kt, kq, thrust, torque, shaft_power, efficiency)


def coefficients_from_measurement(
    point: OperatingPoint, thrust_n: float, torque_nm: float
) -> tuple[float, float]:
    """Recover KT and KQ from a measured open-water operating point."""
    if not all(isfinite(x) for x in (thrust_n, torque_nm)):
        raise ValueError("Thrust and torque must be finite.")
    n = point.revolutions_per_second
    if n == 0:
        raise ValueError("Cannot recover coefficients at zero RPM.")
    t_scale, q_scale = dimensional_scales(point)
    if t_scale == 0 or q_scale == 0:
        raise ValueError("Coefficient denominator underflow.")
    return (finite_value(thrust_n / t_scale), finite_value(torque_nm / q_scale))


def interpolate_coefficients(
    measured_j: Iterable[float],
    measured_kt: Iterable[float],
    measured_kq: Iterable[float],
    requested_j: float,
) -> tuple[float, float]:
    """Linear interpolation only: refusing extrapolation beyond measured J."""
    x = np.asarray(list(measured_j), dtype=float)
    kt = np.asarray(list(measured_kt), dtype=float)
    kq = np.asarray(list(measured_kq), dtype=float)
    if len(x) < 2 or len(x) != len(kt) or len(x) != len(kq):
        raise ValueError("At least two equally sized measurements required.")
    if not (np.isfinite(x).all() and np.isfinite(kt).all()
            and np.isfinite(kq).all() and np.isfinite(requested_j)):
        raise ValueError("Measurement data must be finite.")
    if x.ndim != 1 or kt.ndim != 1 or kq.ndim != 1:
        raise ValueError("Coefficient arrays must be one-dimensional.")
    order = np.argsort(x)
    x, kt, kq = x[order], kt[order], kq[order]
    if np.any(x < 0):
        raise ValueError("J must be nonnegative.")
    if np.any(np.diff(x) <= 0):
        raise ValueError("Measured J values must be unique.")
    if not x[0] <= requested_j <= x[-1]:
        raise ValueError("Requested J outside measured range; extrapolation disabled.")
    return float(np.interp(requested_j, x, kt)), float(np.interp(requested_j, x, kq))


def performance_status(result: Performance) -> str:
    """Retain signed measurements and raw eta, but flag invalid propulsion regimes."""
    if result.advance_coefficient is None:
        return "zero_rpm_no_prediction"
    if result.kt < 0 or result.kq <= 0:
        return "outside_forward_propulsion"
    if result.efficiency is not None and result.efficiency > 1:
        return "efficiency_above_one"
    return "definitions_only_not_validated"
