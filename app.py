"""MarineProp Studio v0.1 — research prototype."""
from __future__ import annotations

import io

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
    st.caption("Motor elektrik gücü ile şaft gücü aynı değildir.")

tab_point, tab_curves, tab_data = st.tabs([
    "Çalışma noktası", "Katsayı eğrileri", "Ölçüm verisi"
])

with tab_point:
    st.subheader("Verilen açık su katsayılarından performans")
    st.info("Aşağıdaki katsayılar gösterim amaçlıdır; doğrulanmış bir pervaneye ait değildir.")
    col_a, col_b = st.columns(2)
    kt = col_a.number_input("İtme katsayısı KT", value=0.12, format="%.5f")
    kq = col_b.number_input("Tork katsayısı KQ", value=0.025, format="%.5f")
    p = OperatingPoint(diameter, rpm, va, rho)
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
        "density_kg_m3": rho, **result.__dict__,
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
        except (ValueError, pd.errors.ParserError, UnicodeError) as exc:
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
            from marineprop import coefficients_from_measurement
            df = pd.read_csv(measured)
            required = ["rpm", "advance_speed_m_s", "thrust_n", "torque_nm"]
            if not set(required).issubset(df.columns):
                raise ValueError("Gerekli sütunlar: " + ", ".join(required))
            df[required] = df[required].apply(pd.to_numeric, errors="raise")
            if not np.isfinite(df[required].to_numpy()).all():
                raise ValueError("Tüm veriler sonlu olmalıdır.")
            j_values, kt_values, kq_values = [], [], []
            for row in df.itertuples(index=False):
                point = OperatingPoint(diameter, getattr(row, "rpm"),
                                       getattr(row, "advance_speed_m_s"), rho)
                kti, kqi = coefficients_from_measurement(
                    point, getattr(row, "thrust_n"), getattr(row, "torque_nm"))
                j_values.append(point.advance_coefficient)
                kt_values.append(kti)
                kq_values.append(kqi)
            df["J"], df["KT"], df["KQ"] = j_values, kt_values, kq_values
            st.dataframe(df, use_container_width=True)
            st.download_button("Boyutsuzlaştırılmış verileri indir", df.to_csv(index=False).encode(),
                               file_name="marineprop_measured_coefficients.csv", mime="text/csv")
        except (ValueError, pd.errors.ParserError, UnicodeError) as exc:
            st.error(f"Ölçüm verisi işlenemedi: {exc}")

st.caption("MarineProp Studio v0.1 — sonuçlar mühendislik doğrulaması gerektirir.")
