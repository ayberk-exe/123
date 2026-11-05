"""Validated CSV transformations shared by UI and batch workflows."""
import numpy as np
import pandas as pd
from .core import OperatingPoint, calculate, coefficients_from_measurement


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
    results = []
    for row in data.itertuples(index=False):
        point = OperatingPoint(diameter_m, row.rpm, row.advance_speed_m_s,
                               density_kg_m3, viscosity_m2_s)
        kt, kq = coefficients_from_measurement(point, row.thrust_n, row.torque_nm)
        result = calculate(point, kt, kq)
        results.append(dict(J=result.advance_coefficient, KT=kt, KQ=kq,
                            shaft_power_w=result.shaft_power_w, eta0=result.efficiency,
                            Re_n=point.rotational_reynolds_number))
    return pd.concat([data.reset_index(drop=True), pd.DataFrame(results)], axis=1)
