"""MarineProp Studio v0.1 — research prototype."""
from __future__ import annotations

from dataclasses import asdict
from marineprop.data import measurement_table
from marineprop.vessel import itu_green_ship_project

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from marineprop import OperatingPoint, calculate, interpolate_coefficients


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

with tab_point:
    st.subheader("Verilen açık su katsayılarından performans")
    st.info("Aşağıdaki katsayılar gösterim amaçlıdır; doğrulanmış bir pervaneye ait değildir.")
    col_a, col_b = st.columns(2)
    kt = col_a.number_input("İtme katsayısı KT", value=0.12, format="%.5f")
    kq = col_b.number_input("Tork katsayısı KQ", value=0.025, format="%.5f")
    p = OperatingPoint(diameter, rpm, va, rho, nu)
    result = calculate(p, kt, kq)
    a, b, c, d = st.columns(4)
    a.metric("İtme T", f"{result.thrust_n:.3f} N")
    b.metric("Tork Q", f"{result.torque_nm:.4f} N·m")
    c.metric("Şaft gücü", f"{result.shaft_power_w:.2f} W")
    d.metric("Açık su verimi", "Tanımsız" if result.efficiency is None else f"{result.efficiency:.1%}")
    st.write("İlerleme katsayısı J:", "Tanımsız (n = 0)" if result.advance_coefficient is None
             else f"{result.advance_coefficient:.4f}")
    if result.efficiency is not None and result.efficiency > 1:
        st.error("Hesaplanan verim %100'ü aşıyor: katsayı/çalışma noktası fiziksel olarak tutarsız.")
    if result.efficiency is None:
        st.warning("Bu çalışma noktasında açık su verimi tanımlı değil.")
    export = pd.DataFrame([{
        "diameter_m": diameter, "rpm": rpm, "advance_speed_m_s": va,
        "density_kg_m3": rho, "kinematic_viscosity_m2_s": nu, **result.__dict__,
    }])
    st.download_button("Çalışma noktasını CSV indir", export.to_csv(index=False).encode(),
                       file_name="marineprop_operating_point.csv", mime="text/csv")

with tab_curves:
    st.subheader("Kullanıcı tanımlı KT(J), KQ(J) eğrileri")
    st.caption("Katsayı verisi biliniyorsa aşağıdaki CSV şablonuyla yükleyin.")
    example = pd.DataFrame({
        "J": [0.0, 0.2, 0.4, 0.6, 0.8],
        "KT": [0.18, 0.16, 0.13, 0.09, 0.04],
        "KQ": [0.035, 0.032, 0.028, 0.023, 0.016],
    })
    st.download_button("Temsili CSV şablonu indir", example.to_csv(index=False).encode(),
                       file_name="synthetic_coefficients.csv", mime="text/csv")
    uploaded = st.file_uploader("J, KT, KQ sütunlu CSV yükle", type="csv", key="coeff")
    if uploaded is not None:
        try:
            data = pd.read_csv(uploaded)
            if not {"J", "KT", "KQ"}.issubset(data.columns):
                raise ValueError("CSV sütunları J, KT, KQ olmalıdır.")
            data = data[["J", "KT", "KQ"]].apply(pd.to_numeric, errors="raise").sort_values("J")
            if len(data) < 2 or data.isna().any().any() or not np.isfinite(data.to_numpy()).all():
                raise ValueError("En az iki sonlu sayısal veri noktası gerekir.")
            if data["J"].duplicated().any() or (data["J"] < 0).any():
                raise ValueError("J değerleri benzersiz ve negatif olmayan sayılar olmalıdır.")
            if (data["KQ"] <= 0).any():
                st.warning("KQ <= 0 olan yerlerde verim hesaplanmıyor.")
            data["eta0"] = np.where(
                (data["KQ"] > 0) & (data["KT"] >= 0),
                data["J"] * data["KT"] / (2 * np.pi * data["KQ"]), np.nan
            )
            data["advance_speed_m_s"] = data["J"] * p.revolutions_per_second * diameter
            data["thrust_n"] = data["KT"] * rho * p.revolutions_per_second**2 * diameter**4
            data["torque_nm"] = data["KQ"] * rho * p.revolutions_per_second**2 * diameter**5
            data["shaft_power_w"] = 2 * np.pi * p.revolutions_per_second * data["torque_nm"]
            st.caption("Boyutlu eğriler yan paneldeki sabit RPM ve çap için hesaplanır. J boyunca ilerleme hızı değişir.")
            fig = go.Figure()
            for column in ("KT", "KQ", "eta0"):
                fig.add_trace(go.Scatter(x=data["J"], y=data[column], mode="lines+markers", name=column))
            fig.update_layout(xaxis_title="İlerleme katsayısı J (-)",
                              yaxis_title="Boyutsuz katsayı (-)", legend_title="Eğri")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(data, use_container_width=True)
            st.download_button("Hesaplanmış eğrileri indir",
                               data.to_csv(index=False).encode(),
                               file_name="marineprop_curves.csv", mime="text/csv")
            if p.advance_coefficient is not None:
                try:
                    kt_i, kq_i = interpolate_coefficients(data["J"], data["KT"], data["KQ"],
                                                          p.advance_coefficient)
                    current = calculate(p, kt_i, kq_i)
                    st.success(f"J={p.advance_coefficient:.3f}: T={current.thrust_n:.3f} N, "
                               f"Q={current.torque_nm:.4f} N·m, P={current.shaft_power_w:.2f} W")
                except ValueError as exc:
                    st.warning(str(exc))
        except (ValueError, pd.errors.ParserError, UnicodeError, TypeError, OverflowError) as exc:
            st.error(f"CSV okunamadı: {exc}")

with tab_data:
    st.subheader("Deneysel ölçüm verisi")
    st.write("Ölçüm şeması: rpm, advance_speed_m_s, thrust_n, torque_nm. "
             "Çap ve yoğunluk yan panelden alınır.")
    template = pd.DataFrame({
        "rpm": [1500, 2000, 2500],
        "advance_speed_m_s": [0.5, 0.7, 0.9],
        "thrust_n": [0.6, 1.0, 1.6],
        "torque_nm": [0.008, 0.015, 0.024],
    })
    st.download_button("Temsili ölçüm şablonunu indir", template.to_csv(index=False).encode(),
                       file_name="synthetic_measurements.csv", mime="text/csv")
    measured = st.file_uploader("Ölçüm CSV yükle", type="csv", key="measure")
    if measured is not None:
        try:
            df = measurement_table(pd.read_csv(measured), diameter, rho, nu)
            st.dataframe(df, use_container_width=True)
            st.download_button("Boyutsuzlaştırılmış verileri indir", df.to_csv(index=False).encode(),
                               file_name="marineprop_measured_coefficients.csv", mime="text/csv")
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
    st.metric("Section Reynolds Re_0.7R", f"{p.blade_reynolds_number(chord):,.0f}")
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
    pb = OperatingPoint(d2, rpm2, va, rho, nu)
    comparison = pd.DataFrame([
        {"propeller": "A", **asdict(p), **asdict(result)},
        {"propeller": "B", **asdict(pb), **asdict(calculate(pb, kt2, kq2))},
    ])
    st.dataframe(comparison, use_container_width=True)
    fig_compare = go.Figure(go.Bar(x=comparison["propeller"], y=comparison["thrust_n"]))
    fig_compare.update_layout(xaxis_title="Pervane", yaxis_title="İtme (N)")
    st.plotly_chart(fig_compare, use_container_width=True)
    st.download_button("Karşılaştırmayı CSV indir", comparison.to_csv(index=False).encode(), "comparison.csv", "text/csv")

with tab_settings:
    st.subheader("ITU Green Ship — çift T60 veri hazırlığı")
    project = itu_green_ship_project()
    st.json(asdict(project))
    st.warning("T60 performans verisi sağlanmadı. Toplam itme, elektrik tüketimi veya gemi hızı tahmin edilmiyor.")
    st.download_button("Proje şemasını JSON indir", __import__('json').dumps(asdict(project), indent=2), "itu_green_ship.json", "application/json")
    st.write("Gelecek modüller: 3D geometri, STL/STEP, BEMT, kavitasyon, motor eşleştirme, OpenFOAM, optimizasyon ve raporlama. Henüz uygulanmadı.")
