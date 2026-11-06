"""Validated CSV transformations shared by UI and batch workflows."""
import numpy as np
import pandas as pd
from .core import OperatingPoint, calculate, coefficients_from_measurement, performance_status


def numeric_columns(frame, columns):
    if frame.empty or not set(columns).issubset(frame.columns):
        raise ValueError('Nonempty data required with columns: ' + ', '.join(columns))
    if frame.columns.duplicated().any():
        raise ValueError('Duplicate column names are not supported.')
    data = frame.loc[:, columns].apply(pd.to_numeric, errors='raise').copy()
    if not np.isfinite(data.to_numpy()).all():
        raise ValueError('All measurements must be finite.')
    return data


def measurement_table(frame, diameter_m, density_kg_m3, viscosity_m2_s=1.004e-6):
    data = numeric_columns(frame, ['rpm', 'advance_speed_m_s', 'thrust_n', 'torque_nm'])
    optional = [c for c in ('electrical_power_w', 'motor_efficiency') if c in frame.columns]
    if optional:
        extra = numeric_columns(frame, optional).reset_index(drop=True)
        if 'electrical_power_w' in extra and (extra.electrical_power_w < 0).any():
            raise ValueError('Electrical power must be nonnegative.')
        if 'motor_efficiency' in extra and ((extra.motor_efficiency <= 0) | (extra.motor_efficiency > 1)).any():
            raise ValueError('Motor efficiency must be in (0, 1].')
        data = pd.concat([data.reset_index(drop=True), extra], axis=1)
    results = []
    for row in data.itertuples(index=False):
        point = OperatingPoint(diameter_m, row.rpm, row.advance_speed_m_s,
                               density_kg_m3, viscosity_m2_s)
        kt, kq = coefficients_from_measurement(point, row.thrust_n, row.torque_nm)
        result = calculate(point, kt, kq)
        results.append(dict(J=result.advance_coefficient, KT=kt, KQ=kq,
                            shaft_power_w=result.shaft_power_w, eta0=result.efficiency,
                            Re_n=point.rotational_reynolds_number, status=performance_status(result)))
    output = pd.concat([data.reset_index(drop=True), pd.DataFrame(results)], axis=1)
    if 'electrical_power_w' in output:
        output['shaft_to_electrical_ratio'] = np.nan
        mask = output.electrical_power_w > 0
        output.loc[mask, 'shaft_to_electrical_ratio'] = output.loc[mask, 'shaft_power_w'] / output.loc[mask, 'electrical_power_w']
        invalid = ((output.shaft_power_w > output.electrical_power_w) | (output.shaft_power_w < 0))
        output.loc[invalid, 'status'] = 'inconsistent_electrical_power'
    return output


def coefficient_table(frame):
    data = numeric_columns(frame, ['J', 'KT', 'KQ']).sort_values('J').reset_index(drop=True)
    from .core import interpolate_coefficients
    interpolate_coefficients(data.J, data.KT, data.KQ, float(data.J.iloc[0]))
    return data


def curve_table(frame, point):
    """Evaluate coefficients at fixed RPM/D; never extrapolate or apply scale correction."""
    from .core import performance_status
    data = coefficient_table(frame)
    rows = []
    for row in data.itertuples(index=False):
        speed = float(row.J) * point.revolutions_per_second * point.diameter_m
        p = OperatingPoint(point.diameter_m, point.rpm, speed,
                           point.density_kg_m3, point.kinematic_viscosity_m2_s)
        r = calculate(p, row.KT, row.KQ)
        rows.append(dict(J=row.J, KT=row.KT, KQ=row.KQ, eta0=r.efficiency,
                         advance_speed_m_s=speed, thrust_n=r.thrust_n,
                         torque_nm=r.torque_nm, shaft_power_w=r.shaft_power_w,
                         status=performance_status(r)))
    return pd.DataFrame(rows)


def experimental_performance(frame, point):
    from .core import interpolate_coefficients
    data = coefficient_table(frame)
    if point.advance_coefficient is None:
        raise ValueError('Deneysel eğri değerlendirmesi için RPM > 0 gerekir.')
    kt, kq = interpolate_coefficients(data.J, data.KT, data.KQ, point.advance_coefficient)
    return calculate(point, kt, kq)
