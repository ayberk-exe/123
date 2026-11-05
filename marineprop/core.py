"""MarineProp Studio computational core. SI units throughout."""
from __future__ import annotations

from dataclasses import dataclass
from math import pi, isfinite
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class OperatingPoint:
    diameter_m: float
    rpm: float
    advance_speed_m_s: float
    density_kg_m3: float = 998.2

    def __post_init__(self) -> None:
        for field in ("diameter_m", "rpm", "advance_speed_m_s", "density_kg_m3"):
            value = getattr(self, field)
            if not isfinite(value):
                raise ValueError(f"{field} must be finite")
        if self.diameter_m <= 0 or self.density_kg_m3 <= 0:
            raise ValueError("Diameter and density must be positive.")
        if self.rpm < 0 or self.advance_speed_m_s < 0:
            raise ValueError("RPM and advance speed must be nonnegative.")

    @property
    def revolutions_per_second(self) -> float:
        return self.rpm / 60.0

    @property
    def advance_coefficient(self) -> float | None:
        n = self.revolutions_per_second
        return self.advance_speed_m_s / (n * self.diameter_m) if n > 0 else None


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
    n, d, rho = point.revolutions_per_second, point.diameter_m, point.density_kg_m3
    j = point.advance_coefficient
    thrust = kt * rho * n**2 * d**4
    torque = kq * rho * n**2 * d**5
    shaft_power = 2 * pi * n * torque
    efficiency = None
    if j is not None and kq > 0 and kt >= 0:
        efficiency = j * kt / (2 * pi * kq)
    return Performance(j, kt, kq, thrust, torque, shaft_power, efficiency)


def coefficients_from_measurement(
    point: OperatingPoint, thrust_n: float, torque_nm: float
) -> tuple[float, float]:
    """Recover KT and KQ from a measured open-water operating point."""
    if not all(isfinite(x) for x in (thrust_n, torque_nm)):
        raise ValueError("Thrust and torque must be finite.")
    n, d, rho = point.revolutions_per_second, point.diameter_m, point.density_kg_m3
    if n == 0:
        raise ValueError("Cannot recover coefficients at zero RPM.")
    return (thrust_n / (rho * n**2 * d**4),
            torque_nm / (rho * n**2 * d**5))


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
    order = np.argsort(x)
    x, kt, kq = x[order], kt[order], kq[order]
    if np.any(np.diff(x) <= 0):
        raise ValueError("Measured J values must be unique.")
    if not x[0] <= requested_j <= x[-1]:
        raise ValueError("Requested J outside measured range; extrapolation disabled.")
    return float(np.interp(requested_j, x, kt)), float(np.interp(requested_j, x, kq))
