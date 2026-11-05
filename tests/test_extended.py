import io
import math
import pandas as pd
import pytest
from marineprop import OperatingPoint, calculate, interpolate_coefficients
from marineprop.data import measurement_table
from marineprop.vessel import itu_green_ship_project, ThrusterSample, VesselProject


def test_reynolds_definitions():
    p = OperatingPoint(0.1, 600, 1, 1000, 1e-6)
    assert p.rotational_reynolds_number == pytest.approx(100000)
    assert p.blade_reynolds_number(0.02) == pytest.approx(math.hypot(1, 0.7*math.pi)*0.02/1e-6)
    with pytest.raises(ValueError):
        OperatingPoint(0.1, 600, 1, 1000, 0)
    with pytest.raises(ValueError):
        p.blade_reynolds_number(float('nan'))


def test_scaling_and_energy_identity():
    a = calculate(OperatingPoint(0.1, 600, 1), .15, .03)
    b = calculate(OperatingPoint(0.2, 600, 2), .15, .03)
    assert b.thrust_n == pytest.approx(16*a.thrust_n)
    assert b.torque_nm == pytest.approx(32*a.torque_nm)
    assert a.efficiency == pytest.approx(a.thrust_n / a.shaft_power_w)
    assert b.efficiency == pytest.approx(a.efficiency)


def test_csv_roundtrip_and_empty_rejection():
    p = OperatingPoint(.06, 3000, 1.5)
    r = calculate(p, .12, .025)
    csv = f'rpm,advance_speed_m_s,thrust_n,torque_nm\n3000,1.5,{r.thrust_n},{r.torque_nm}\n'
    table = measurement_table(pd.read_csv(io.StringIO(csv)), .06, 998.2)
    assert table.KT.iloc[0] == pytest.approx(.12)
    assert table.KQ.iloc[0] == pytest.approx(.025)
    assert pd.read_csv(io.StringIO(table.to_csv(index=False))).shape == table.shape
    with pytest.raises(ValueError):
        measurement_table(pd.read_csv(io.StringIO(csv)).iloc[:0], .06, 998.2)
    with pytest.raises(ValueError):
        measurement_table(pd.read_csv(io.StringIO(csv)).assign(rpm=0), .06, 998.2)


def test_no_fabricated_t60_data():
    project = itu_green_ship_project()
    assert len(project.thrusters) == 2
    assert all(not t.samples for t in project.thrusters)
    assert project.wake_fraction is None
    with pytest.raises(ValueError):
        ThrusterSample(1000, 0, 1, .1, motor_efficiency=1.1)
    with pytest.raises(ValueError):
        VesselProject('bad', project.thrusters, (1, 0), (2, 3))


def test_unsorted_and_negative_j():
    assert interpolate_coefficients([1,0], [.1,.2], [.01,.02], .5) == pytest.approx((.15,.015))
    with pytest.raises(ValueError):
        interpolate_coefficients([-1,0], [.1,.2], [.01,.02], 0)
