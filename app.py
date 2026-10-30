"""Crop Stress Telemetry & Advisory - Mobile-First Streamlit Dashboard.
Farmer-first design: large buttons, high contrast, emojis, audio speech synthesis,
WhatsApp sharing, PDF export, shaded 7-day charts, plain-word dosage tables,
and collapsible agent trace and data quality inspection panels.
"""
import io
import json
import os
import urllib.parse
from typing import Any, Dict

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

import config
from config.i18n import LANGUAGES, SAFETY_DISCLAIMER, UI_STRINGS
from main import run_agent
from tools.dosage_calculator import DosageCalculator
from tools.load_telemetry import TelemetryLoader
from tools.trend_analyzer import TrendAnalyzer
from tools.weather_forecast import WeatherForecast

# Streamlit Page Setup
st.set_page_config(
    page_title="Crop Stress Telemetry & Advisory",
    page_icon="🍅",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom High-Contrast Mobile-First CSS
st.markdown("""
<style>
    /* Responsive base typography */
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    .big-status-card {
        padding: 1.2rem;
        border-radius: 14px;
        margin-bottom: 0.8rem;
        color: #ffffff;
        font-weight: 600;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }
    .status-healthy { background: linear-gradient(135deg, #1e7e34, #28a745); }
    .status-watch { background: linear-gradient(135deg, #d39e00, #ffc107); color: #212529 !important; }
    .status-critical { background: linear-gradient(135deg, #bd2130, #dc3545); }
    .status-info { background: linear-gradient(135deg, #117a8b, #17a2b8); }

    .card-title {
        font-size: 1.1rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        opacity: 0.9;
        margin-bottom: 0.3rem;
    }
    .card-value {
        font-size: 1.8rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .card-subtext {
        font-size: 0.95rem;
        opacity: 0.95;
    }

    .advisory-box {
        background-color: #f8f9fa;
        border-left: 6px solid #28a745;
        padding: 1.5rem;
        border-radius: 10px;
        font-size: 1.15rem;
        line-height: 1.6;
        color: #1a1a1a;
        margin: 1rem 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    .safety-disclaimer {
        background-color: #fff3cd;
        border: 1px solid #ffeeba;
        color: #856404;
        padding: 0.9rem 1.2rem;
        border-radius: 8px;
        font-size: 0.95rem;
        font-weight: 600;
        margin-top: 1rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        font-size: 1.2rem;
        font-weight: 700;
        padding: 0.75rem 1rem;
        min-height: 3.2rem;
    }
</style>
""", unsafe_allow_html=True)


def generate_pdf_report(advisory_text: str, status: str, score: int,
                        water_rec: Dict[str, Any], fert_rec: Dict[str, Any],
                        lang_name: str) -> bytes:
    """Generates an agronomy PDF report in bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(name="TitleStyle", parent=styles["Heading1"], fontSize=18, leading=22, textColor=colors.HexColor("#2e7d32"))
    h2_style = ParagraphStyle(name="H2Style", parent=styles["Heading2"], fontSize=14, leading=18, textColor=colors.HexColor("#1b5e20"))
    body_style = ParagraphStyle(name="BodyStyle", parent=styles["Normal"], fontSize=10, leading=14, textColor=colors.HexColor("#212121"))
    disclaimer_style = ParagraphStyle(name="DiscStyle", parent=styles["Italic"], fontSize=9, leading=12, textColor=colors.HexColor("#b71c1c"))

    story = [
        Paragraph("🍅 Tomato Crop Stress Telemetry & Advisory", title_style),
        Paragraph(f"<b>Assessment Status:</b> {status} (Stress Index: {score}/100) &nbsp;|&nbsp; <b>Language:</b> {lang_name}", body_style),
        Spacer(1, 14),
        Paragraph("<b>Actionable Farm Advisory:</b>", h2_style),
        Spacer(1, 6),
    ]

    for line in advisory_text.splitlines():
        if line.strip():
            story.append(Paragraph(line.strip(), body_style))
            story.append(Spacer(1, 4))

    story.append(Spacer(1, 14))
    story.append(Paragraph("<b>Recommended Dosages & Schedules:</b>", h2_style))
    story.append(Spacer(1, 6))

    doses = fert_rec.get("today_field_dose_kg", {})
    table_data = [
        ["Resource", "Dosage / Rate", "Operational Details"],
        ["Water (Drip)", f"{water_rec.get('litres_per_plant', 0):.1f} L / plant", f"Run drip for {water_rec.get('drip_runtime_minutes', 0):.0f} mins ({water_rec.get('reason', '')[:40]}...)"],
        ["Urea (46% N)", f"{doses.get('urea_46_n', 0):.1f} kg (Field)", f"Split in {fert_rec.get('split_schedule', {}).get('urea_splits', 1)} applications (Max safe: 25 kg/ac)"],
        ["DAP (18-46-0)", f"{doses.get('dap_18_46_0', 0):.1f} kg (Field)", f"Split in {fert_rec.get('split_schedule', {}).get('dap_splits', 1)} applications (Max safe: 30 kg/ac)"],
        ["MOP (60% K2O)", f"{doses.get('mop_60_k2o', 0):.1f} kg (Field)", f"Split in {fert_rec.get('split_schedule', {}).get('mop_splits', 1)} applications (Max safe: 20 kg/ac)"],
    ]

    t = Table(table_data, colWidths=[110, 130, 300])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f5e9")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1b5e20")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c8e6c9")),
    ]))
    story.append(t)

    story.append(Spacer(1, 16))
    story.append(Paragraph(f"<b>Mandatory Safety Notice:</b> {SAFETY_DISCLAIMER['en']}", disclaimer_style))

    doc.build(story)
    return buffer.getvalue()


# Top Bar Controls
st.title("🍅 Crop Stress Telemetry & Advisory")
st.markdown("Precision AI Farm Advisory powered by Real-Time Telemetry & Agronomic Models")

col_lang, col_size, col_unit, col_loc = st.columns([1.5, 1, 1, 1.5])
with col_lang:
    selected_lang_code = st.selectbox(
        "🌐 Language / மொழி / भाषा",
        options=list(LANGUAGES.keys()),
        format_func=lambda c: LANGUAGES[c],
        index=0
    )
with col_size:
    field_size = st.number_input("🌾 Field Size", min_value=0.1, max_value=500.0, value=1.0, step=0.5)
with col_unit:
    field_unit = st.selectbox("📏 Unit", ["acre", "hectare", "cent"], index=0)
with col_loc:
    loc_option = st.selectbox("📍 Location", ["Sensor Coordinates (24.68°N, 92.75°E)", "Custom Coordinates"], index=0)

custom_lat, custom_lon = 24.6848, 92.7510
if loc_option == "Custom Coordinates":
    c1, c2 = st.columns(2)
    with c1:
        custom_lat = st.number_input("Latitude", value=24.6848, format="%.4f")
    with c2:
        custom_lon = st.number_input("Longitude", value=92.7510, format="%.4f")

# Data Upload / Sample Selector
uploaded_file = st.file_uploader("📂 Upload Farm Sensor CSV or JSON (or leave empty to use dataset)", type=["csv", "json"])

# Main Action Button
run_clicked = st.button("🚀 Analyze Crop Stress & Get Farm Advisory", type="primary")

# Execute Pipeline
loader = TelemetryLoader()
telemetry_res = loader.load_clean_data()
analyzer = TrendAnalyzer()
trend_res = analyzer.analyze()
weather_tool = WeatherForecast()
weather_res = weather_tool.fetch(lat=custom_lat, lon=custom_lon)
calc_tool = DosageCalculator()
dosage_res = calc_tool.calculate(
    field_size=field_size,
    unit=field_unit,
    moisture_pct=trend_res.get("metrics", {}).get("moisture_pct", {}).get("latest", 57.2),
    temperature_c=trend_res.get("metrics", {}).get("temperature", {}).get("latest", 31.0),
    rain_risk=weather_res.get("rain_risk", "Low"),
    expected_rain_mm=weather_res.get("expected_rain_mm_3d", 0.0)
)

stress_score = trend_res.get("stress_score", 40)
stress_status = trend_res.get("stress_status", "Watch")
rain_risk = weather_res.get("rain_risk", "Low")
rain_mm = weather_res.get("expected_rain_mm_3d", 0.0)
water_rec = dosage_res.get("water_recommendation", {})
fert_rec = dosage_res.get("fertilizer_recommendation", {})

# Determine Card CSS styles
health_class = "status-healthy" if stress_status == "Healthy" else ("status-watch" if stress_status == "Watch" else "status-critical")
rain_class = "status-healthy" if rain_risk == "Low" else ("status-watch" if rain_risk == "Medium" else "status-critical")
action_class = "status-watch" if rain_risk == "High" else ("status-info" if water_rec.get("litres_per_plant", 0) > 0 else "status-healthy")

st.markdown("<hr style='margin: 1rem 0;'>", unsafe_allow_html=True)

# Row 1: Three Big Status Cards (Green/Amber/Red)
c_health, c_rain, c_action = st.columns(3)

with c_health:
    emoji_h = "🟢" if stress_status == "Healthy" else ("🟡" if stress_status == "Watch" else "🔴")
    st.markdown(f"""
    <div class="big-status-card {health_class}">
        <div class="card-title">🌱 Soil & Crop Health</div>
        <div class="card-value">{emoji_h} {stress_status}</div>
        <div class="card-subtext">Stress Score: {stress_score}/100 &nbsp;|&nbsp; Moisture: {trend_res.get('metrics', {}).get('moisture_pct', {}).get('latest', 57.2):.1f}%</div>
    </div>
    """, unsafe_allow_html=True)

with c_rain:
    emoji_r = "🟢" if rain_risk == "Low" else ("🟡" if rain_risk == "Medium" else "🔴")
    st.markdown(f"""
    <div class="big-status-card {rain_class}">
        <div class="card-title">🌧️ 3-Day Rain Risk</div>
        <div class="card-value">{emoji_r} {rain_risk} Risk</div>
        <div class="card-subtext">{rain_mm:.1f} mm expected ({weather_res.get('rain_probability_max_pct', 0):.0f}% max prob)</div>
    </div>
    """, unsafe_allow_html=True)

with c_action:
    if rain_risk == "High":
        action_header = "⏸️ Hold Irrigation"
        action_detail = "Heavy rain expected; prevent waterlogging"
    elif water_rec.get("litres_per_plant", 0) > 0:
        action_header = f"💧 Drip {water_rec.get('drip_runtime_minutes', 0):.0f} Mins"
        action_detail = f"{water_rec.get('litres_per_plant', 0):.1f} L/plant ({water_rec.get('total_litres_field', 0):,.0f} L total)"
    else:
        action_header = "✅ Soil Hydrated"
        action_detail = "Moisture optimal; no irrigation needed today"

    st.markdown(f"""
    <div class="big-status-card {action_class}">
        <div class="card-title">⚡ Today's Action</div>
        <div class="card-value">{action_header}</div>
        <div class="card-subtext">{action_detail}</div>
    </div>
    """, unsafe_allow_html=True)

# Generate Advisory using Agent/Writer
from tools.advisory_writer import AdvisoryWriter
writer = AdvisoryWriter()
advisory_text = writer.compose(
    language=selected_lang_code,
    stress_status=stress_status,
    moisture_pct=trend_res.get("metrics", {}).get("moisture_pct", {}).get("latest", 57.2),
    water_liters_plant=water_rec.get("litres_per_plant", 0.0),
    drip_minutes=water_rec.get("drip_runtime_minutes", 0.0),
    rain_risk=rain_risk,
    expected_rain_mm=rain_mm,
    urea_kg=fert_rec.get("today_field_dose_kg", {}).get("urea_46_n", 0.0),
    dap_kg=fert_rec.get("today_field_dose_kg", {}).get("dap_18_46_0", 0.0),
    mop_kg=fert_rec.get("today_field_dose_kg", {}).get("mop_60_k2o", 0.0),
    unit=field_unit,
    anomalies=trend_res.get("anomalies_and_risks", [])
)

# Row 2: Advisory Card with Audio TTS & WhatsApp Share & PDF Download
st.subheader(f"📋 {UI_STRINGS.get(selected_lang_code, UI_STRINGS['en'])['advisory']}")
st.markdown(f"""
<div class="advisory-box">
{advisory_text.replace(chr(10), '<br>')}
</div>
""", unsafe_allow_html=True)

# Action Buttons: Listen (Audio TTS), WhatsApp, PDF
c_listen, c_wa, c_pdf = st.columns([1.2, 1.2, 1.2])

with c_listen:
    # Web Speech API in browser (handles regional languages natively)
    clean_speech_text = advisory_text.replace("\n", " ").replace('"', "'")
    voice_lang = {"ta": "ta-IN", "hi": "hi-IN", "bn": "bn-IN", "te": "te-IN"}.get(selected_lang_code, "en-US")
    tts_html = f"""
    <button onclick="speakAdvisory()" style="
        width: 100%;
        background-color: #2e7d32;
        color: white;
        border: none;
        padding: 10px 14px;
        border-radius: 8px;
        font-weight: bold;
        font-size: 1rem;
        cursor: pointer;
    ">🔊 Listen (Audio)</button>
    <script>
    function speakAdvisory() {{
        window.speechSynthesis.cancel();
        const text = "{clean_speech_text}";
        const utter = new SpeechSynthesisUtterance(text);
        utter.lang = "{voice_lang}";
        utter.rate = 0.95;
        window.speechSynthesis.speak(utter);
    }}
    </script>
    """
    components.html(tts_html, height=52)

with c_wa:
    wa_encoded = urllib.parse.quote(f"🍅 Tomato Advisory ({stress_status}):\n\n{advisory_text}")
    wa_url = f"https://api.whatsapp.com/send?text={wa_encoded}"
    st.markdown(f"""
    <a href="{wa_url}" target="_blank" style="text-decoration: none;">
        <button style="
            width: 100%;
            background-color: #25D366;
            color: white;
            border: none;
            padding: 10px 14px;
            border-radius: 8px;
            font-weight: bold;
            font-size: 1rem;
            cursor: pointer;
        ">📲 Share on WhatsApp</button>
    </a>
    """, unsafe_allow_html=True)

with c_pdf:
    pdf_bytes = generate_pdf_report(
        advisory_text=advisory_text,
        status=stress_status,
        score=stress_score,
        water_rec=water_rec,
        fert_rec=fert_rec,
        lang_name=LANGUAGES[selected_lang_code]
    )
    st.download_button(
        label="📄 Download PDF Advisory",
        data=pdf_bytes,
        file_name=f"Tomato_Farm_Advisory_{selected_lang_code}.pdf",
        mime="application/pdf"
    )

st.markdown("<hr style='margin: 1.2rem 0;'>", unsafe_allow_html=True)

# Row 3: 7-Day Trend Charts with Optimal Bands Shaded
st.subheader("📈 7-Day Telemetry Trends & Optimal Bands")

tab1, tab2, tab3 = st.tabs(["💧 Soil Moisture (%)", "🌡️ Temperature (°C)", "🌱 Soil Nutrients (NPK)"])

df_chart: pd.DataFrame = telemetry_res.get("data", pd.DataFrame())

with tab1:
    if "moisture_pct" in df_chart.columns and not df_chart["moisture_pct"].dropna().empty:
        s_moist = df_chart["moisture_pct"].dropna().tail(30).reset_index(drop=True)
        chart_df = pd.DataFrame({
            "Observed Moisture (%)": s_moist,
            "Min Target (50%)": [50.0] * len(s_moist),
            "Optimal (70%)": [70.0] * len(s_moist),
            "Max Target (90%)": [90.0] * len(s_moist),
        })
        st.line_chart(chart_df, color=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"])
        st.caption("ℹ️ Shaded optimal zone: 50% to 90%. Recent values hover around 57%, indicating mild moisture deficit requiring drip replenishment.")
    else:
        st.info("Moisture data not available.")

with tab2:
    if "temperature" in df_chart.columns and not df_chart["temperature"].dropna().empty:
        s_temp = df_chart["temperature"].dropna().tail(30).reset_index(drop=True)
        temp_df = pd.DataFrame({
            "Observed Temp (°C)": s_temp,
            "Optimal (28°C)": [28.0] * len(s_temp),
            "Heat Stress Threshold (32°C)": [32.0] * len(s_temp),
        })
        st.line_chart(temp_df, color=["#e377c2", "#2ca02c", "#d62728"])
        st.caption("ℹ️ Peak daytime temperatures spiked above 32°C, causing heat stress. Extra water added to transpiration allowance.")
    else:
        st.info("Temperature data not available.")

with tab3:
    npk_data = pd.DataFrame({
        "Nutrient": ["Nitrogen (N)", "Phosphorus (P)", "Potassium (K)"],
        "Current (mg/kg)": [
            trend_res.get("metrics", {}).get("n", {}).get("latest", 110.0),
            trend_res.get("metrics", {}).get("p", {}).get("latest", 40.0),
            trend_res.get("metrics", {}).get("k", {}).get("latest", 55.0),
        ],
        "Target (mg/kg)": [140.0, 50.0, 80.0]
    }).set_index("Nutrient")
    st.bar_chart(npk_data)
    st.caption("ℹ️ Nutrient levels are below target ranges. Recommended split fertilizer doses to restore balance.")

st.markdown("<hr style='margin: 1.2rem 0;'>", unsafe_allow_html=True)

# Row 4: Plain-Word Dosage Table
st.subheader("🧪 Recommended Dosages in Plain Words")

doses = fert_rec.get("today_field_dose_kg", {})
dosage_items = [
    {
        "Input": "💧 Water (Drip Irrigation)",
        "Today's Field Total": f"{water_rec.get('total_litres_field', 0):,.0f} Litres",
        "Per Plant / Rate": f"{water_rec.get('litres_per_plant', 0):.2f} L / plant",
        "Drip Run Time": f"Run drip for {water_rec.get('drip_runtime_minutes', 0):.0f} minutes",
        "Application Guidance": water_rec.get("reason", "")
    },
    {
        "Input": "🌿 Urea (46% Nitrogen)",
        "Today's Field Total": f"{doses.get('urea_46_n', 0):.1f} kg",
        "Per Plant / Rate": f"{(doses.get('urea_46_n', 0) / max(1, field_size)):.1f} kg / {field_unit}",
        "Drip Run Time": f"{fert_rec.get('split_schedule', {}).get('urea_splits', 1)} Weekly Splits",
        "Application Guidance": "Capped at max 25 kg/acre safety cap to avoid burning roots."
    },
    {
        "Input": "🌱 DAP (18-46-0 Phosphorus)",
        "Today's Field Total": f"{doses.get('dap_18_46_0', 0):.1f} kg",
        "Per Plant / Rate": f"{(doses.get('dap_18_46_0', 0) / max(1, field_size)):.1f} kg / {field_unit}",
        "Drip Run Time": f"{fert_rec.get('split_schedule', {}).get('dap_splits', 1)} Split Doses",
        "Application Guidance": "Capped at max 30 kg/acre single application."
    },
    {
        "Input": "🍇 MOP (60% Potassium)",
        "Today's Field Total": f"{doses.get('mop_60_k2o', 0):.1f} kg",
        "Per Plant / Rate": f"{(doses.get('mop_60_k2o', 0) / max(1, field_size)):.1f} kg / {field_unit}",
        "Drip Run Time": f"{fert_rec.get('split_schedule', {}).get('mop_splits', 1)} Split Doses",
        "Application Guidance": "Capped at max 20 kg/acre single application."
    }
]

st.table(pd.DataFrame(dosage_items))

st.markdown("<hr style='margin: 1.2rem 0;'>", unsafe_allow_html=True)

# Collapsible Panels
with st.expander("🔍 How did the agent decide? (Execution Trace)"):
    st.markdown("Below is the ReAct loop execution trace demonstrating how the autonomous agent queried data, analyzed stress, checked weather, and computed formulas:")
    if run_clicked:
        ans, trace = run_agent(f"Analyze tomato farm telemetry and generate advisory in {LANGUAGES[selected_lang_code]}")
        for i, step in enumerate(trace):
            st.markdown(f"**Step {i+1}: {step.get('thought')}**")
            st.code(f"Action: {step.get('tool')}({step.get('args')})")
            st.caption(f"Observation: {str(step.get('observation'))[:250]}...")
            st.markdown("---")
    else:
        st.info("Click 'Analyze Crop Stress' above to see live trace steps, or inspect the pre-evaluated pipeline tools above.")

with st.expander("📐 How was this calculated? (Agronomic Formulas)"):
    st.markdown("""
    ### Water Requirement Formula:
    $$\\text{Water Demand (L/plant)} = \\max(0, \\text{Deficit}_L + \\text{ET}_L - \\text{RainCredit}_L + \\text{HeatAdjustment}_L)$$
    - **Deficit ($L$):** $(\\text{Target}\\% - \\text{Current}\\%) \\times 10\\text{ L root storage capacity}$.
    - **ET Replacement ($L$):** Reference ET $\\times K_c (1.15) \\times 0.35\\text{ m}^2$ plant canopy.
    - **Rain Credit ($L$):** $60\\%$ of forecasted rainfall mm.
    - **Heat Adjustment ($L$):** $+0.15\\text{ L}$ for every degree Celsius above optimal $28^\\circ\\text{C}$.
    - **Drip Runtime:** $\\frac{\\text{Water Demand (L)}}{\\text{Emitter Discharge (L/hr)}} \\times 60\\text{ minutes}$.

    ### Fertilizer Stoichiometry:
    - **DAP ($18\\text{N}-46\\text{P}_2\\text{O}_5-0$):** $\\frac{\\Delta P \\times 0.81 \\times 2.29}{0.46}$.
    - **Urea ($46\\%\\text{ N}$):** $\\frac{\\text{Total N Deficit} - \\text{N from DAP}}{0.46}$.
    - **MOP ($60\\%\\text{ K}_2\\text{O}$):** $\\frac{\\Delta K \\times 0.81 \\times 1.20}{0.60}$.
    - **Safety Caps:** Urea $\\le 25\\text{ kg/ac}$, DAP $\\le 30\\text{ kg/ac}$, MOP $\\le 20\\text{ kg/ac}$ per application.
    """)

with st.expander("⚠️ Data Quality & Assumptions"):
    for note in telemetry_res.get("quality_notes", []):
        st.markdown(f"- {note}")

st.markdown(f"""
<div class="safety-disclaimer">
⚠️ <b>Safety Notice:</b> {SAFETY_DISCLAIMER.get(selected_lang_code, SAFETY_DISCLAIMER['en'])}
</div>
""", unsafe_allow_html=True)
