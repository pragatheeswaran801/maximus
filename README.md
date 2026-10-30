# 🍅 Crop Stress Telemetry & Precision Farm Advisory

> An autonomous, agronomy-grounded ReAct AI agent and mobile-first Streamlit dashboard that turns raw tomato telemetry and microclimate data into actionable farm advisories, exact irrigation run-times, and fertilizer split schedules.

---

## 🌟 Overview & Key Capabilities

1. **Autonomous ReAct Agent (`main.py`)**:
   - Implements the strict Judging Contract: `python main.py --json "<query>"` outputs **exactly ONE line of valid JSON** to stdout: `{"answer": "...", "trace": [...]}`.
   - Grounded in real tools: inspects telemetry, detects sensor faults, analyzes trends, forecasts rain, and computes deterministic water & fertilizer dosages. Never hallucinates numbers.
2. **Robust Multi-Source Ingestion (`load_telemetry`)**:
   - Case-insensitive, fuzzy column matching across heterogeneous CSV and JSON schemas.
   - Ordinary least squares calibration ($moisture\_pct = -0.0963 \times raw + 99.18, R^2 = 0.8987$).
   - Flags biologically implausible values (e.g. soil pH outside 3.5–9.5) as sensor hardware faults and excludes them from advisory math.
   - Slices the 7-day rolling window ending at the latest dataset timestamp (with fallback to the last 7 distinct planted days).
3. **Deterministic Agronomic Math (`dosage_calculator`)**:
   - **Water**: Calculates exact liters/plant and total field liters based on moisture deficit, root zone capacity (10 L), ET replacement ($K_c = 1.15$), rainfall offset ($60\%$), and heat stress thermal adjustment ($+0.15$ L per degree over 28°C). Converts to drip emitter runtime in minutes.
   - **Fertilizer**: Stoichiometric conversion of N-P-K soil deficits into commercial **Urea** (46% N), **DAP** (18-46-0), and **MOP** (60% $K_2O$) with single-dose safety caps (Urea $\le 25$ kg/ac, DAP $\le 30$ kg/ac, MOP $\le 20$ kg/ac) and split schedules.
   - **Rain Delay Safety**: High rain risk ($\ge 70\%$ prob or $> 15$ mm) automatically delays irrigation and holds chemical fertilizers to prevent root suffocation, anaerobic soil conditions, and nutrient leaching.
4. **Multilingual Advisory & Offline Fallback (`advisory_writer`, `config/i18n.py`)**:
   - Spoken-style concise advisories (max ~120 words: what is wrong, what to do today, this week, what to avoid) in **English**, **Tamil (`ta`)**, **Hindi (`hi`)**, **Bengali (`bn`)**, and **Telugu (`te`)**.
   - Offline template fallback when LLM API keys are absent or rate-limited.
   - Every advisory enforces the mandatory safety notice: *"Confirm with your local agriculture officer before applying."*
5. **Farmer-First Streamlit Dashboard (`app.py`)**:
   - High-contrast green/amber/red status badges for **Soil Health**, **Rain Risk**, and **Today's Action**.
   - Built-in text-to-speech audio reader (Web Speech API).
   - One-click WhatsApp share and PDF report download.
   - 7-day trend visualizations with shaded optimal target bands.
   - Plain-word dosage tables and collapsible decision trace/data quality panels.

---

## 🏗️ Architecture

```mermaid
flowchart TD
    subgraph Data Sources [data/ or AGENTX_DATA_DIR]
        CSV[tomato_irrigation_dataset.csv\nRaw moisture 120-700, NPK, pH]
        JSON[tomato_water_sensor_data.json\nMoisture pairs, coordinates, drip flow, timestamps]
        REF[Crop_recommendation.csv\n22 crops benchmark ranges]
    end

    subgraph Agent Tools [tools/]
        T1[load_telemetry\nCalibration R2=0.8987, pH anomaly filter, 7d window]
        T2[trend_analyzer\nSlopes, leak detection, heat stress, Stress Score 0-100]
        T3[weather_forecast\nOpen-Meteo 3-day forecast, rain risk, offline fallback]
        T4[dosage_calculator\nDeterministic water L/plant, drip runtime min, Urea/DAP/MOP dosage, rain delay]
        T5[crop_reference_lookup\nBenchmark query and sanity checks]
        T6[advisory_writer\nLLM wording + Multilingual templates EN/TA/HI/BN/TE + safety line]
    end

    subgraph Agent Core [agent/]
        PB[prompt_builder.py\nTomato farm advisor persona]
        AG[core.py ReAct Executor\nJudging contract compliant]
    end

    subgraph User Interfaces
        CLI[main.py CLI\n--json stdout contract: single line JSON]
        ST[app.py Streamlit\nMobile-first, KPI cards, TTS audio, WhatsApp, PDF, Trace]
    end

    Data Sources --> T1
    REF --> T5
    T1 --> T2
    T1 --> T4
    T3 --> T4
    T2 & T3 & T4 & T5 --> T6
    Agent Tools --> AG
    PB --> AG
    AG --> CLI
    AG --> ST
```

---

## 🚀 Quickstart & Installation

### 1. Requirements
Ensure Python 3.10+ is installed:
```bash
pip install -r requirements.txt
```

### 2. Environment Configuration
Create a `.env` file (optional for LLM mode; dry-run works 100% offline without API keys):
```ini
GEMINI_API_KEY=your_gemini_api_key_here
# or
GROQ_API_KEY=your_groq_api_key_here

# Optional: custom data directory
# AGENTX_DATA_DIR=./data
```

---

## 💻 CLI Usage (Judging Contract)

### 1. Machine JSON Contract (`--json`)
Prints **exactly ONE line of valid JSON** to stdout; logs to stderr:
```bash
python main.py --json "What is the tomato crop health and water requirement?"
```
**Output shape:**
```json
{"answer": "Status: Watch tomato crop stress.\nToday's Action: Soil moisture is low at 57.2%. Apply 3.2 L/plant by running drip for 84 minutes.\nThis Week (Fertilizer): Apply 25.0 kg Urea, 30.0 kg DAP, and 20.0 kg MOP per acre in split doses.\nWhat to Avoid: Avoid fertilizing right before rain or irrigating during peak afternoon heat.\nSafety: Confirm with your local agriculture officer before applying.", "trace": [{"thought": "...", "tool": "load_telemetry", "args": {}, "observation": "..."}, ...]}
```

### 2. Multilingual Queries
```bash
# Hindi
python main.py --json "टमाटर की फसल में सिंचाई और खाद की क्या सलाह है?"

# Tamil
python main.py --json "தக்காளி பயிர் உர மேலாண்மை மற்றும் பாசன ஆலோசனை தருக"
```

### 3. Human-Readable Run
```bash
python main.py "Assess tomato stress and give water dosage for 2 acres"
```

---

## 📱 Mobile-First Streamlit Dashboard

Run the interactive dashboard:
```bash
streamlit run app.py
```

### Key UI Features:
- **Top Bar**: Language dropdown (English, Tamil, Hindi, Bengali, Telugu), Field Size input, Unit (acre/hectare/cent), Location selector.
- **Row 1 - Status Cards**: 3 high-contrast cards (Soil Health, 3-Day Rain Risk, Today's Action).
- **Row 2 - Farmer Advisory**: Formatted card with **🔊 Listen (TTS)** button, **📲 Share on WhatsApp**, and **📄 Download PDF Advisory**.
- **Row 3 - 7-Day Trend Charts**: Shaded optimum bands (Moisture 50–90%, Temperature 20–28°C) and N-P-K comparison bars.
- **Row 4 - Plain-Word Dosage Table**: Plain English dosage and drip runtime instructions.
- **Collapsed Panels**: Execution trace, mathematical formulas, and data quality/sensor fault logs.

---

## 🧪 Running the Unit Tests

All unit tests run **100% offline** with zero external network dependencies:
```bash
python -m unittest discover tests -v
```

### Test Coverage:
1. `tests/test_telemetry.py`: Schema normalization, calibration fit $R^2$, pH anomaly detection (<3.5 or >9.5 excluded), duplicate removal, 7-day temporal window slicing.
2. `tests/test_dosage.py`: Zero deficit handling, heavy rain delay rules, extreme heat adjustment, fertilizer stoichiometry, safety caps, and unit conversions.
3. `tests/test_weather.py`: Open-Meteo offline fallback, rain risk classification, manual rain override.
4. `tests/test_agent.py`: End-to-end ReAct loop, repeat guards, max iteration cap, safety line enforcement, and exact `--json` single-line stdout contract.

---

## 📊 Assumptions & Future Improvements

### Current Assumptions:
1. **Evapotranspiration & Irrigation Units**: Sensor telemetry ET values are assumed in mm/day; water flow rate is assumed in Liters/hour; dripper spacing is assumed in cm.
2. **Soil pH Viability**: Values outside 3.5–9.5 are biologically impossible for arable agricultural soils and represent hardware ADC/sensor faults; they are excluded from soil advice.
3. **Tomato Population**: Standard determinate field tomato density is assumed at 12,000 plants/acre (~30,000 plants/ha).

### Recommended Future Enhancements:
1. **Pest & Disease Forewarning**: Integrate humidity-duration thresholds with temperature (e.g. Blight risk index when RH > 85% for > 10 hours).
2. **Automated Solenoid Control**: Link the calculated drip runtime to an MQTT IoT smart valve actuator for hands-free irrigation.
3. **Soil Texture Inputs**: Allow farmers to select soil texture (Sandy loam vs Clay loam) to dynamically modulate root-zone field capacity.
