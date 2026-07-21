import math

import streamlit as st
from streamlit_autorefresh import st_autorefresh
import pandas as pd

from JIT_core import SimulationSession, _default_test_inputs, JITState


st.set_page_config(page_title="JIT Simulation", layout="wide")


DEFAULTS = _default_test_inputs()

# Performance: maximum number of points to keep for live charts
MAX_HISTORY_POINTS = 200


def _collect_inputs_from_session_state() -> dict:
    return {
        "vehicle_speed_kmh": st.session_state["vehicle_speed_kmh"],
        "initial_distance_m": st.session_state["initial_distance_m"],
        "obstacle_closing_speed_ms": st.session_state["obstacle_closing_speed_ms"],
        "road_friction": st.session_state["road_friction"],
        "rain_detected": st.session_state["rain_detected"],
        "camera_confidence": st.session_state["camera_confidence"],
        "driver_override": st.session_state["driver_override"],
    }


# --- session_state defaults ---
if "ui_mode" not in st.session_state:
    st.session_state.ui_mode = "idle"
if "session" not in st.session_state:
    st.session_state.session = None
if "last_snapshot" not in st.session_state:
    st.session_state.last_snapshot = None


# --- Sidebar inputs (use keys so we can programmatically reset) ---
st.sidebar.header("Simulation Inputs")
st.sidebar.slider("Vehicle speed (km/h)", 40, 120, int(DEFAULTS["vehicle_speed_kmh"]), key="vehicle_speed_kmh")
st.sidebar.slider("Initial distance (m)", 10, 100, int(DEFAULTS["initial_distance_m"]), key="initial_distance_m")
st.sidebar.slider("Obstacle closing speed (m/s)", 0, 20, int(DEFAULTS["obstacle_closing_speed_ms"]), key="obstacle_closing_speed_ms")
st.sidebar.slider("Road friction (μ)", 0.2, 0.8, float(DEFAULTS["road_friction"]), step=0.01, key="road_friction")
st.sidebar.checkbox("Rain detected", value=DEFAULTS["rain_detected"], key="rain_detected")
st.sidebar.slider("Camera confidence", 0.0, 1.0, float(DEFAULTS["camera_confidence"]), step=0.01, key="camera_confidence")
st.sidebar.checkbox("Driver override", value=DEFAULTS["driver_override"], key="driver_override")
st.sidebar.markdown("---")
# allow user to tune refresh for responsiveness
st.sidebar.slider("Refresh interval (ms)", 50, 1000, 200, step=50, key="refresh_interval")


# --- Control buttons ---
st.sidebar.markdown("---")
col_run, col_stop, col_reset = st.sidebar.columns([1, 1, 1])
with col_run:
    run_pressed = st.button("RUN")
with col_stop:
    stop_pressed = st.button("STOP")
with col_reset:
    reset_pressed = st.button("RESET")


if run_pressed:
    # create and reset session with current input values
    session = SimulationSession(dt=0.1)
    inputs = _collect_inputs_from_session_state()
    session.reset(inputs, seed=42)
    st.session_state.session = session
    st.session_state.ui_mode = "live"
    st.session_state.last_snapshot = None

if stop_pressed:
    st.session_state.ui_mode = "stopped"

if reset_pressed:
    # force idle and clear
    sess = st.session_state.get("session")
    if sess is not None:
        try:
            sess.force_idle()
        except Exception:
            pass
    st.session_state.session = None
    st.session_state.ui_mode = "idle"
    st.session_state.last_snapshot = None


# --- Live stepping (autorefresh only when live) ---
if st.session_state.ui_mode == "live":
    refresh_ms = int(st.session_state.get("refresh_interval", 200))
    st_autorefresh(interval=refresh_ms, key="autorefresh")
    sess = st.session_state.get("session")
    if sess is not None:
        inputs = _collect_inputs_from_session_state()
        snapshot = sess.step(inputs)
        st.session_state.last_snapshot = snapshot
else:
    snapshot = st.session_state.get("last_snapshot")


# --- First row outputs ---
st.title("JIT Simulation — Live Dashboard")

def _state_color(s: JITState) -> str:
    return {
        JITState.IDLE: "#2ecc71",
        JITState.THREAT_CANDIDATE: "#f39c12",
        JITState.SUPPRESSED: "#95a5a6",
        JITState.ACTUATING: "#e74c3c",
        JITState.OVERRIDDEN: "#3498db",
        JITState.DEGRADED_CAMERA: "#f1c40f",
    }.get(s, "#bdc3c7")


col1, col2, col3, col4 = st.columns(4)

current_state = JITState.IDLE
ttc_actual = math.inf
ttc_min = math.inf
warning_stage = "—"

if snapshot is not None:
    current_state = snapshot["state"]
    ttc_actual = snapshot["ttc_actual"]
    ttc_min = snapshot["ttc_min"]

    if current_state == JITState.ACTUATING:
        warning_stage = "BRAKE ENGAGED"
    elif current_state == JITState.THREAT_CANDIDATE:
        warning_stage = "THREAT"
    elif current_state == JITState.SUPPRESSED:
        warning_stage = "SUPPRESSED"
    elif current_state == JITState.DEGRADED_CAMERA:
        warning_stage = "DEGRADED CAMERA"
    elif current_state == JITState.OVERRIDDEN:
        warning_stage = "OVERRIDDEN"
    else:
        warning_stage = "IDLE"

with col1:
    color = _state_color(current_state)
    st.markdown(f"<div style='background:{color};padding:12px;border-radius:6px'>"
                f"<h3 style='margin:0'>{current_state.value}</h3></div>", unsafe_allow_html=True)
with col2:
    val = "∞" if ttc_actual == math.inf else f"{ttc_actual:.2f} s"
    st.metric("TTC Actual", val)
with col3:
    val2 = "∞" if ttc_min == math.inf else f"{ttc_min:.2f} s"
    st.metric("TTC Minimum", val2)
with col4:
    st.metric("Warning Stage", warning_stage)


st.markdown("---")

# --- Live traces and history ---
if snapshot is not None:
    # build safe arrays (session snapshot may provide either scalar ttc_min or list ttc_mins)
    times = list(snapshot.get("times", []))
    distances = list(snapshot.get("distances", []))
    ttc_actuals = list(snapshot.get("ttc_actuals", []))
    ttc_mins = list(snapshot.get("ttc_mins", [])) if snapshot.get("ttc_mins") is not None else [snapshot.get("ttc_min", math.inf)] * len(times)
    brakes = list(snapshot.get("brake_engagement", []))

    # Performance: limit history size to avoid large DataFrames and slow rendering
    if len(times) > MAX_HISTORY_POINTS:
        start = max(0, len(times) - MAX_HISTORY_POINTS)
        times = times[start:]
        distances = distances[start:]
        ttc_actuals = ttc_actuals[start:]
        ttc_mins = ttc_mins[start:]
        brakes = brakes[start:]

        if len(times) > 0:
            st.subheader("Live traces")
            # TTC chart (actual vs minimum)
            ttc_df = pd.DataFrame({"TTC Actual": ttc_actuals, "TTC Minimum": ttc_mins}, index=times)
            st.line_chart(ttc_df, height=260, use_container_width=True)

        col_d, col_b = st.columns([2, 1])
        with col_d:
            dist_df = pd.DataFrame({"Distance (m)": distances}, index=times)
            st.line_chart(dist_df, height=220, use_container_width=True)
        with col_b:
            brake_df = pd.DataFrame({"Brake Level": brakes}, index=times)
            st.line_chart(brake_df, height=220, use_container_width=True)

        # Recent state history
        st.subheader("Recent states")
        states = [s.value if hasattr(s, "value") else str(s) for s in snapshot.get("states", [])]
        recent_n = 10
        recent_rows = []
        for i, t in enumerate(times[-recent_n:]):
            idx = len(times) - recent_n + i
            if idx < 0:
                idx = i
            state_label = states[idx] if idx < len(states) else "-"
            recent_rows.append({"time (s)": f"{t:.2f}", "state": state_label})
        st.table(recent_rows)

if st.session_state.ui_mode == "idle":
    st.info("Simulation is IDLE. Press RUN to start.")
