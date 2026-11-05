"""Experimental data contracts; no T60 model or hull correction is assumed."""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class ThrusterSample:
    rpm: float
    advance_speed_m_s: float
    thrust_n: float
    torque_nm: float
    electrical_power_w: float | None = None
    motor_efficiency: float | None = None

    def __post_init__(self):
        for name in ('rpm', 'advance_speed_m_s', 'thrust_n', 'torque_nm'):
            if not isfinite(getattr(self, name)):
                raise ValueError(f'{name} must be finite')
        if self.rpm < 0 or self.advance_speed_m_s < 0:
            raise ValueError('Forward-operation samples require nonnegative speed and RPM')
        if self.electrical_power_w is not None and (not isfinite(self.electrical_power_w) or self.electrical_power_w < 0):
            raise ValueError('Electrical power must be finite and nonnegative')
        if self.motor_efficiency is not None and (not isfinite(self.motor_efficiency) or not 0 < self.motor_efficiency <= 1):
            raise ValueError('Motor efficiency must be in (0, 1]')


@dataclass(frozen=True)
class ThrusterDataset:
    name: str
    source: str
    samples: tuple[ThrusterSample, ...] = ()


@dataclass(frozen=True)
class VesselProject:
    name: str
    thrusters: tuple[ThrusterDataset, ThrusterDataset]
    resistance_speed_m_s: tuple[float, ...] = ()
    resistance_n: tuple[float, ...] = ()
    wake_fraction: float | None = None
    thrust_deduction_fraction: float | None = None

    def __post_init__(self):
        if len(self.thrusters) != 2:
            raise ValueError('Exactly two thrusters required')
        x, y = self.resistance_speed_m_s, self.resistance_n
        if len(x) != len(y) or any(not isfinite(v) or v < 0 for v in (*x, *y)):
            raise ValueError('Resistance data must be paired, finite and nonnegative')
        if any(b <= a for a, b in zip(x, x[1:])):
            raise ValueError('Resistance speeds must be strictly increasing')
        for value in (self.wake_fraction, self.thrust_deduction_fraction):
            if value is not None and (not isfinite(value) or not 0 <= value < 1):
                raise ValueError('Interaction fractions must be in [0, 1)')


def itu_green_ship_project():
    return VesselProject('ITU Green Ship', (
        ThrusterDataset('Port T60', 'Not supplied'),
        ThrusterDataset('Starboard T60', 'Not supplied')))
