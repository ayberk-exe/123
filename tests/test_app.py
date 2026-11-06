from streamlit.testing.v1 import AppTest


def test_six_tabs_and_interactive_recalculation():
    app = AppTest.from_file('../app.py').run(timeout=30)
    assert not app.exception
    assert len(app.tabs) == 6
    assert len(app.get('plotly_chart')) == 1
    assert len(app.get('download_button')) == 5
    metric = lambda: next(m.value for m in app.metric if m.label == "İtme T")
    rpm = next(w for w in app.number_input if w.label == "Şaft devri (RPM)")
    before = metric()
    rpm.set_value(1500.0).run()
    assert not app.exception
    assert metric() != before
    next(w for w in app.number_input if w.label == "Şaft devri (RPM)").set_value(0.0).run()
    assert not app.exception
    assert metric() == '0.000 N'


def test_csv_interface_paths(monkeypatch):
    import io
    import streamlit as st
    def upload(label, **kwargs):
        if kwargs['key'] == 'coeff':
            return io.StringIO('J,KT,KQ\n0,.2,.03\n1,.05,.015\n')
        return io.StringIO('rpm,advance_speed_m_s,thrust_n,torque_nm\n3000,1.5,3.88,.0485\n')
    monkeypatch.setattr(st, 'file_uploader', upload)
    app = AppTest.from_file('../app.py').run(timeout=30)
    assert not app.exception
    assert not app.error
    assert len(app.get('plotly_chart')) == 3
    assert len(app.get('download_button')) == 7
    assert len(app.success) == 1
    assert any('shaft_power_w' in frame.value.columns for frame in app.dataframe)


def test_malformed_csv_shows_error(monkeypatch):
    import io
    import streamlit as st
    monkeypatch.setattr(st, 'file_uploader', lambda *a, **k: io.StringIO('wrong\n1\n'))
    app = AppTest.from_file('../app.py').run(timeout=30)
    assert not app.exception
    assert len(app.error) == 2


def test_analysis_methods_and_no_fallback(monkeypatch):
    import io
    import streamlit as st
    def upload(*args, **kwargs):
        return io.StringIO('J,KT,KQ\n0,.2,.04\n1,.1,.02\n') if kwargs['key']=='coeff' else None
    monkeypatch.setattr(st,'file_uploader',upload)
    app=AppTest.from_file('../app.py').run(timeout=30)
    method=next(w for w in app.selectbox if w.label=='Analiz yöntemi')
    method.select('B — Deneysel açık su CSV').run()
    assert not app.exception
    thrust=next(m.value for m in app.metric if m.label=='İtme T')
    assert thrust=='4.851 N'
    next(w for w in app.number_input if w.label=='İlerleme hızı VA (m/s)').set_value(4.0).run()
    assert not app.exception
    assert not any(m.label=='İtme T' for m in app.metric)
    assert any('extrapolation' in e.value for e in app.error)
    next(w for w in app.selectbox if w.label=='Analiz yöntemi').select('C — Doğrulanmış seri (kullanılamıyor)').run()
    assert not app.exception
    assert not any(m.label=='İtme T' for m in app.metric)


def test_missing_experimental_data_and_bad_efficiency():
    app=AppTest.from_file('../app.py').run(timeout=30)
    next(w for w in app.selectbox if w.label=='Analiz yöntemi').select('B — Deneysel açık su CSV').run()
    assert not app.exception
    assert not any(m.label=='İtme T' for m in app.metric)
    next(w for w in app.selectbox if w.label=='Analiz yöntemi').select('A — Kullanıcı KT/KQ').run()
    next(w for w in app.number_input if w.label=='Tork katsayısı KQ').set_value(.0001).run()
    assert not app.exception
    assert any('%100' in e.value for e in app.error)


def test_fluid_scale_chord_and_comparison_updates():
    import pytest
    app=AppTest.from_file('../app.py').run(timeout=30)
    def set_number(label,value):
        next(w for w in app.number_input if w.label==label).set_value(value).run()
        assert not app.exception
    def comparison():
        return next(d.value for d in app.dataframe if 'propeller' in d.value.columns)
    original=comparison()
    set_number('Yoğunluk ρ (kg/m³)',1996.4)
    doubled=comparison()
    assert doubled.thrust_n.iloc[0]==pytest.approx(2*original.thrust_n.iloc[0])
    set_number('Kinematik viskozite ν (m²/s)',2.008e-6)
    assert comparison().thrust_n.iloc[0]==pytest.approx(doubled.thrust_n.iloc[0])
    ren=next(m.value for m in app.metric if m.label=='Rotational Reynolds Re_n')
    assert ren=='89,641'
    section=next(m.value for m in app.metric if m.label=='Section Reynolds Re_0.7R')
    set_number('0.7R kesit kord uzunluğu (m)',.02)
    assert float(next(m.value for m in app.metric if m.label=='Section Reynolds Re_0.7R').replace(',','')) == pytest.approx(2*float(section.replace(',','')),abs=1)
    set_number('Pervane B devri (RPM)',1200.)
    assert comparison().thrust_n.iloc[1]==pytest.approx(doubled.thrust_n.iloc[1]/4)
    next(w for w in app.selectbox if w.label=='Ölçek').select('Tam ölçek').run()
    assert not app.exception
    assert not any('Reynolds etkileri nedeniyle' in w.value for w in app.warning)


def test_extreme_ui_input_is_reported():
    app=AppTest.from_file('../app.py').run(timeout=30)
    next(w for w in app.number_input if w.label=='Çap D (m)').set_value(1e100).run()
    assert not app.exception
    assert any('aralık' in e.value for e in app.error)
