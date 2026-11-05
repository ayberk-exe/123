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
    assert len(app.get('plotly_chart')) == 2
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
