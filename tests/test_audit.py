"""Regression cases from engineering audit, independent analytic expectations."""
import io
import math
import pandas as pd
import pytest
from marineprop import OperatingPoint, calculate, coefficients_from_measurement, interpolate_coefficients
from marineprop.core import performance_status
from marineprop.data import coefficient_table, curve_table, experimental_performance, measurement_table


@pytest.mark.parametrize('kt,kq,status,eta', [
    (.2,.04,'definitions_only_not_validated',1/(2*math.pi)),
    (-.2,.04,'outside_forward_propulsion',None),
    (.2,-.04,'outside_forward_propulsion',None),
    (.2,0,'outside_forward_propulsion',None),
    (1,.001,'efficiency_above_one',.2/(2*math.pi*.001)),
])
def test_signed_coefficients_and_impossible_efficiency(kt,kq,status,eta):
    p = OperatingPoint(1,60,.2,1000)
    r = calculate(p,kt,kq)
    assert r.thrust_n == pytest.approx(kt*1000)
    assert r.torque_nm == pytest.approx(kq*1000)
    assert performance_status(r) == status
    if eta is None:
        assert r.efficiency is None
    else:
        assert r.efficiency == pytest.approx(eta)


def test_bollard_pull_and_full_scale():
    r = calculate(OperatingPoint(2,120,0,1025),.2,.04)
    assert r.advance_coefficient == 0
    assert r.thrust_n == pytest.approx(13120)
    assert r.torque_nm == pytest.approx(5248)
    assert r.shaft_power_w == pytest.approx(4*math.pi*5248)
    assert r.efficiency == 0  # zero useful advance power does not mean zero thrust


@pytest.mark.parametrize('diameter,rpm', [(1e100,3000),(.1,1e200)])
def test_extreme_scales_fail_cleanly(diameter,rpm):
    with pytest.raises(ValueError,match='range'):
        calculate(OperatingPoint(diameter,rpm,1),.1,.02)


def test_underflow_measurements():
    with pytest.raises(ValueError,match='underflow'):
        coefficients_from_measurement(OperatingPoint(1e-100,1e-100,0),1,1)


@pytest.mark.parametrize('field', ['diameter_m','rpm','advance_speed_m_s','density_kg_m3','kinematic_viscosity_m2_s'])
@pytest.mark.parametrize('value', [float('nan'),float('inf'),-1])
def test_invalid_operating_inputs(field,value):
    args=dict(diameter_m=.1,rpm=600,advance_speed_m_s=1,density_kg_m3=1000,kinematic_viscosity_m2_s=1e-6)
    args[field]=value
    with pytest.raises(ValueError):
        OperatingPoint(**args)


def test_nested_interpolation_rejected_before_indexing():
    with pytest.raises(ValueError,match='one-dimensional'):
        interpolate_coefficients([[0,1],[2,3]],[.2,.1],[.03,.02],.5)


def test_experimental_selection_and_no_extrapolation():
    data = pd.DataFrame({'J':[1,0],'KT':[.1,.2],'KQ':[.02,.04]})
    p = OperatingPoint(.1,600,.5,1000)
    r = experimental_performance(data,p)
    assert r.kt == pytest.approx(.15)
    assert r.kq == pytest.approx(.03)
    assert r.thrust_n == pytest.approx(1.5)
    assert r.torque_nm == pytest.approx(.03)
    assert r.efficiency == pytest.approx(1.5*.5/(2*math.pi*10*.03))
    for speed in (1.1,):
        with pytest.raises(ValueError,match='extrapolation'):
            experimental_performance(data,OperatingPoint(.1,600,speed))
    with pytest.raises(ValueError,match='RPM'):
        experimental_performance(data,OperatingPoint(.1,0,0))
    curves = curve_table(data,p)
    assert list(curves.J) == [0,1]
    assert list(curves.advance_speed_m_s) == [0,1]
    assert list(curves.thrust_n) == pytest.approx([2,1])
    assert curve_table(data,OperatingPoint(.1,0,0)).eta0.isna().all()


@pytest.mark.parametrize('csv', ['J,KT,KQ\n0,.1,.02\n0,.2,.03', 'J,KT,KQ\n-1,.1,.02\n0,.2,.03', 'J,KT,KQ\n0,.1,nan\n1,.2,.03', 'J,KT,KQ\n0,.1,.02'])
def test_invalid_curves(csv):
    with pytest.raises(ValueError):
        coefficient_table(pd.read_csv(io.StringIO(csv)))


def test_electrical_measurements_preserved_and_checked():
    frame=pd.DataFrame(dict(rpm=[600],advance_speed_m_s=[.5],thrust_n=[1.5],torque_nm=[.03],electrical_power_w=[3],motor_efficiency=[.8]))
    result=measurement_table(frame,.1,1000)
    assert result.electrical_power_w.iloc[0] == 3
    assert result.motor_efficiency.iloc[0] == .8
    assert result.shaft_to_electrical_ratio.iloc[0] == pytest.approx(2*math.pi*10*.03/3)
    bad=measurement_table(frame.assign(electrical_power_w=1),.1,1000)
    assert bad.status.iloc[0] == 'inconsistent_electrical_power'
    with pytest.raises(ValueError):
        measurement_table(frame.assign(electrical_power_w=-1),.1,1000)
    with pytest.raises(ValueError):
        measurement_table(frame.assign(motor_efficiency=1.1),.1,1000)
