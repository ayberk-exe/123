"""MarineProp Studio v0.1 — research prototype."""
from __future__ import annotations

import json
from dataclasses import asdict
from marineprop.data import measurement_table, coefficient_table, curve_table, experimental_performance
from marineprop.vessel import itu_green_ship_project

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from marineprop import OperatingPoint, calculate
from marineprop.core import performance_status


st.set_page_config(page_title="MarineProp Studio", layout="wide", page_icon="⚓")
st.title("MarineProp Studio")
st.caption("Pervane açık su performansı (open-water performance) | Araştırma prototipi v0.1")
st.warning(
    "Bu yazılım henüz tasarım doğrulamasından geçmedi. KT/KQ katsayıları yalnızca "
    "kullanıcı girdisi veya yüklenen ölçüm verisinden alınır; B-Series modeli henüz yoktur."
)

with st.sidebar:
    st.header("Pervane ve akışkan")
    diameter = st.number_input("Çap D (m)", min_value=0.001, value=0.060, format="%.3f")
    rpm = st.number_input("Şaft devri (RPM)", min_value=0.0, value=3000.0, step=100.0)
    va = st.number_input("İlerleme hızı VA (m/s)", min_value=0.0, value=1.5, step=0.1)
    rho = st.number_input("Yoğunluk ρ (kg/m³)", min_value=0.1, value=998.2, step=1.0)
    nu = st.number_input("Kinematik viskozite ν (m²/s)", min_value=1e-9, value=1.004e-6, format="%.9f")
    scale = st.selectbox("Ölçek", ["Model ölçeği", "Tam ölçek"])
    st.caption("Motor elektrik gücü ile şaft gücü aynı değildir.")

tab_dashboard, tab_point, tab_curves, tab_compare, tab_data, tab_settings = st.tabs([
    "Dashboard", "Pervane Performans Analizi", "Open-Water Characteristics",
    "Pervane Karşılaştırması", "Deneysel Veri Analizi", "Proje Ayarları"
])

def warn_status(result):
    status = performance_status(result)
    if status == "efficiency_above_one":
        st.error("Verim %100'ü aşıyor: katsayılar/ölçümler fiziksel olarak tutarsız; sonuç doğrulanmış değildir.")
    elif status == "outside_forward_propulsion":
        st.warning("KT < 0 veya KQ ≤ 0: ileri itki rejimi dışında; açık su verimi tanımsız.")
    elif status == "zero_rpm_no_prediction":
        st.warning("RPM = 0: J ve verim tanımsız. Sıfır T/Q, windmilling veya durgun pervane tahmini değildir.")


with tab_curves:
    uploaded = st.file_uploader("J, KT, KQ sütunlu CSV yükle", type="csv", key="coeff")
    st.caption("KQ sütunu gerçek KQ olmalı; 10KQ grafiği değerlerini doğrudan kullanmayın. Tek pervane ve uyumlu Reynolds/test koşulları gerekir.")
    coefficient_data = None
    if uploaded is not None:
        try:
            coefficient_data = coefficient_table(pd.read_csv(uploaded))
        except (ValueError, TypeError, OverflowError, UnicodeError) as exc:
            st.error(f"CSV okunamadı: {exc}")

try:
    p = OperatingPoint(diameter, rpm, va, rho, nu)
    _reynolds_check = p.rotational_reynolds_number
    calculate(p, 0.0, 0.0)
except (ValueError, OverflowError) as exc:
    st.error(f"Girdi/nümerik aralık hatası: {exc}")
    st.stop()

with tab_point:
    st.subheader("Açık su performans analizi")
    method = st.selectbox("Analiz yöntemi", ["A — Kullanıcı KT/KQ", "B — Deneysel açık su CSV", "C — Doğrulanmış seri (kullanılamıyor)"])
    st.caption("A: verilen katsayıların boyutlandırılması. B: ölçülen J aralığında doğrusal interpolasyon. C: henüz uygulanmadı.")
    st.info("Aşağıdaki katsayılar gösterim amaçlıdır; doğrulanmış bir pervaneye ait değildir.")
    col_a, col_b = st.columns(2)
    kt = col_a.number_input("İtme katsayısı KT", value=0.12, format="%.5f")
    kq = col_b.number_input("Tork katsayısı KQ", value=0.025, format="%.5f")
    result = None
    try:
        if method.startswith("A"):
            result = calculate(p, kt, kq)
        elif method.startswith("B"):
            if coefficient_data is None:
                st.warning("B yöntemi için Open-Water Characteristics bölümüne geçerli deneysel CSV yükleyin.")
            else:
                result = experimental_performance(coefficient_data, p)
        else:
            st.warning("C kullanılamıyor: yayımlanmış B-Series katsayıları ve geçerlilik sınırları doğrulanmadı. Geometri tahmini yapılmaz.")
    except (ValueError, OverflowError) as exc:
        st.error(f"Performans hesaplanamadı: {exc}")
    if result is not None:
        a, b, c, d = st.columns(4)
        a.metric("İtme T", f"{result.thrust_n:.3f} N")
        b.metric("Tork Q", f"{result.torque_nm:.4f} N·m")
        c.metric("Şaft gücü", f"{result.shaft_power_w:.2f} W")
        d.metric("Açık su verimi", "Tanımsız" if result.efficiency is None else f"{result.efficiency:.1%}")
        st.write("İlerleme katsayısı J:", "Tanımsız (n = 0)" if result.advance_coefficient is None
                 else f"{result.advance_coefficient:.4f}")
        warn_status(result)
        export = pd.DataFrame([{
            "diameter_m": diameter, "rpm": rpm, "advance_speed_m_s": va,
            "density_kg_m3": rho, "kinematic_viscosity_m2_s": nu, "method": method,
            "source_file": getattr(uploaded, "name", "uploaded CSV") if method.startswith("B") else "user coefficients",
            "status": performance_status(result), **asdict(result),
        }])
        st.download_button("Çalışma noktasını CSV indir", export.to_csv(index=False).encode(),
                           file_name="marineprop_operating_point.csv", mime="text/csv", on_click="ignore")

with tab_curves:
    st.subheader("Kullanıcı tanımlı KT(J), KQ(J) eğrileri")
    st.caption("Katsayı verisi biliniyorsa aşağıdaki CSV şablonuyla yükleyin.")
    example = pd.DataFrame({
        "J": [0.0, 0.2, 0.4, 0.6, 0.8],
        "KT": [0.18, 0.16, 0.13, 0.09, 0.04],
        "KQ": [0.035, 0.032, 0.028, 0.023, 0.016],
    })
    st.download_button("Temsili CSV şablonu indir", example.to_csv(index=False).encode(),
                       file_name="synthetic_coefficients.csv", mime="text/csv", on_click="ignore")
    if coefficient_data is not None:
        try:
            data = curve_table(coefficient_data, p)
            st.caption("Sabit RPM ve çap: J boyunca VA değişir. Ölçek/Reynolds düzeltmesi uygulanmaz.")
            if (data["status"] != "definitions_only_not_validated").any():
                st.warning("Eğride geçersiz veya tanımsız itki rejimi var; CSV status sütununu kontrol edin.")
            fig = go.Figure()
            for column in ("KT", "KQ", "eta0"):
                fig.add_trace(go.Scatter(x=data["J"], y=data[column], mode="lines+markers", name=column))
            fig.update_layout(xaxis_title="İlerleme katsayısı J (-)", yaxis_title="Boyutsuz katsayı (-)")
            st.plotly_chart(fig, width="stretch")
            dimensional = go.Figure(go.Scatter(x=data.advance_speed_m_s, y=data.thrust_n, mode="lines+markers", name="T"))
            dimensional.update_layout(xaxis_title="İlerleme hızı VA (m/s)", yaxis_title="İtme T (N)")
            st.plotly_chart(dimensional, width="stretch")
            st.dataframe(data, width="stretch")
            st.download_button("Hesaplanmış eğrileri indir", data.to_csv(index=False).encode(), "marineprop_curves.csv", "text/csv", on_click="ignore")
            try:
                current = experimental_performance(coefficient_data, p)
                warn_status(current)
                st.success(f"Deneysel interpolasyon: J={p.advance_coefficient:.3f}, T={current.thrust_n:.3f} N, Q={current.torque_nm:.4f} N·m, P={current.shaft_power_w:.2f} W")
            except ValueError as exc:
                st.warning(str(exc))
        except (ValueError, OverflowError) as exc:
            st.error(f"Eğri hesaplanamadı: {exc}")

with tab_data:
    st.subheader("Deneysel ölçüm verisi")
    st.write("Ölçüm şeması: rpm, advance_speed_m_s, thrust_n, torque_nm. "
             "Çap, yoğunluk ve viskozite yan panelden alınır. İsteğe bağlı: electrical_power_w, motor_efficiency (0–1). Bu sütunlar korunur; motor verimi otomatik varsayılmaz.")
    template = pd.DataFrame({
        "rpm": [1500, 2000, 2500],
        "advance_speed_m_s": [0.5, 0.7, 0.9],
        "thrust_n": [0.6, 1.0, 1.6],
        "torque_nm": [0.008, 0.015, 0.024],
    })
    st.download_button("Temsili ölçüm şablonunu indir", template.to_csv(index=False).encode(),
                       file_name="synthetic_measurements.csv", mime="text/csv", on_click="ignore")
    measured = st.file_uploader("Ölçüm CSV yükle", type="csv", key="measure")
    if measured is not None:
        try:
            df = measurement_table(pd.read_csv(measured), diameter, rho, nu)
            if (df["status"] != "definitions_only_not_validated").any():
                st.warning("Ölçümlerde geçerlilik/enerji tutarlılığı sorunu var; status sütununu kontrol edin.")
            st.dataframe(df, width="stretch")
            st.download_button("Boyutsuzlaştırılmış verileri indir", df.to_csv(index=False).encode(),
                               file_name="marineprop_measured_coefficients.csv", mime="text/csv", on_click="ignore")
        except (ValueError, pd.errors.ParserError, UnicodeError, TypeError, OverflowError) as exc:
            st.error(f"Ölçüm verisi işlenemedi: {exc}")

st.caption("MarineProp Studio v0.1 — sonuçlar mühendislik doğrulaması gerektirir.")

with tab_dashboard:
    st.subheader("Mühendislik özeti")
    a, b, c = st.columns(3)
    a.metric("İlerleme katsayısı J", "Tanımsız" if p.advance_coefficient is None else f"{p.advance_coefficient:.4f}")
    b.metric("Rotational Reynolds Re_n", f"{p.rotational_reynolds_number:,.0f}")
    c.metric("Ölçek", scale)
    st.caption("Re_n = n D²/ν. Bu değer kanat kesiti Reynolds sayısı değildir.")
    chord = st.number_input("0.7R kesit kord uzunluğu (m)", min_value=0.000001, value=0.01, format="%.6f")
    try:
        st.metric("Section Reynolds Re_0.7R", f"{p.blade_reynolds_number(chord):,.0f}")
    except ValueError as exc:
        st.error(f"Kesit Reynolds hesaplanamadı: {exc}")
    st.caption("Re_0.7R = c √(VA² + (0.7πnD)²)/ν; indüklenmiş hızlar ihmal edilir.")
    if scale == "Model ölçeği":
        st.warning("Reynolds etkileri nedeniyle tam ölçek ampirik eğrileri model pervanelerde hatalı olabilir. Ölçülmüş, benzer Reynolds verisi kullanın; otomatik ölçek düzeltmesi uygulanmaz.")
    st.info("KT/KQ girdileri gösterim amaçlıdır. Geometriye dayalı pervane tahmini yapılmaz.")

with tab_compare:
    st.subheader("İki pervane — aynı akışkan ve ilerleme hızı")
    st.caption("Her pervane için mevcut J ve Reynolds koşuluna uygun katsayılar girin.")
    d2 = st.number_input("Pervane B çapı (m)", min_value=0.001, value=0.08)
    rpm2 = st.number_input("Pervane B devri (RPM)", min_value=0.0, value=2400.0)
    kt2 = st.number_input("Pervane B KT", value=0.12)
    kq2 = st.number_input("Pervane B KQ", value=0.025)
    try:
        pb = OperatingPoint(d2, rpm2, va, rho, nu)
        result_a = calculate(p, kt, kq)
        result_b = calculate(pb, kt2, kq2)
    except (ValueError, OverflowError) as exc:
        st.error(f"Karşılaştırma hesaplanamadı: {exc}")
        st.stop()
    st.caption("Karşılaştırma A yöntemiyle bağımsız katsayılar kullanır; B yöntemi seçimi bu tabloya uygulanmaz.")
    warn_status(result_a)
    warn_status(result_b)
    comparison = pd.DataFrame([
        {"propeller": "A", **asdict(p), **asdict(result_a), "status": performance_status(result_a)},
        {"propeller": "B", **asdict(pb), **asdict(result_b), "status": performance_status(result_b)},
    ])
    st.dataframe(comparison, width="stretch")
    fig_compare = go.Figure(go.Bar(x=comparison["propeller"], y=comparison["thrust_n"]))
    fig_compare.update_layout(xaxis_title="Pervane", yaxis_title="İtme (N)")
    st.plotly_chart(fig_compare, width="stretch")
    st.download_button("Karşılaştırmayı CSV indir", comparison.to_csv(index=False).encode(), "comparison.csv", "text/csv", on_click="ignore")

with tab_settings:
    st.subheader("ITU Green Ship — çift T60 veri hazırlığı")
    project = itu_green_ship_project()
    st.json(asdict(project))
    st.warning("T60 performans verisi sağlanmadı. Toplam itme, elektrik tüketimi veya gemi hızı tahmin edilmiyor.")
    st.download_button("Proje şemasını JSON indir", json.dumps(asdict(project), indent=2), "itu_green_ship.json", "application/json", on_click="ignore")
    st.write("Gelecek modüller: 3D geometri, STL/STEP, BEMT, kavitasyon, motor eşleştirme, OpenFOAM, optimizasyon ve raporlama. Henüz uygulanmadı.")
