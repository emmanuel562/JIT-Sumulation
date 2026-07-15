# JIT Simulation — Handoff Document

## WHO YOU ARE BUILDING FOR

Team Axora. A Nigerian engineering team building JIT (Just In Time) — a retrofit Automatic Emergency Braking system for legacy commercial vehicles in Nigeria. This simulation is a competition demo for COUCH 2025. The builder is Emmanuel, solo developer, using Python + Streamlit in VSCode with GitHub Copilot and Cursor IDE.

## WHAT THIS SIMULATION IS

A browser-based **live** interactive simulation of JIT's decision logic. It is NOT a hardware simulation, NOT a real camera feed, NOT a vehicle dynamics model. It is a demonstration of the sensing → decision → actuation pipeline using simulated inputs. The goal is to make the logic visible to a non-technical competition judge.

**Primary operating mode: Live.** Charts, metrics, and state update continuously while the simulation is running. Moving a slider while live immediately affects the next simulation tick.

## WHAT IT IS NOT

- Not a real-time embedded system simulation
- Not connected to any hardware
- No actual camera or radar feed
- No machine learning running inside it
- The Kalman filter models sensor noise smoothing only — it is not an ML model

## TECH STACK

- Language: Python 3.11+
- UI framework: Streamlit
- Charts: Plotly
- Kalman filter: filterpy (`filterpy.kalman.KalmanFilter`)
- Math/physics: numpy
- Auto-refresh: `streamlit-autorefresh` (drives live timestep advancement)
- Camera: OpenCV placeholder only — button exists but is disabled
- IDE: VSCode + Cursor + GitHub Copilot
- Environment: Python virtual environment (venv)
- Version control: GitHub

## FILE STRUCTURE

```
jit_simulation/
│
├── venv/              ← virtual environment, never touch
├── app.py             ← Streamlit entry point, UI only
├── jit_core.py        ← All simulation logic, no UI code
├── requirements.txt   ← All dependencies
├── handoff.md         ← This document
└── README.md          ← Project description
```

## STRICT SEPARATION RULE

`jit_core.py` contains zero Streamlit code. Zero UI code. Pure logic only. `app.py` contains zero physics or decision logic. UI only. It imports from `jit_core.py` and calls its functions.

Never break this separation. If you are tempted to put a calculation inside `app.py`, stop and put it in `jit_core.py` instead.

---

## SIMULATION CONTROL MODES

The dashboard has three UI control states. These are separate from the JIT system states (IDLE, ACTUATING, etc.).

| UI Mode | Description |
|-------|-------------|
| **IDLE** | Simulation is stopped. System state is forced to `IDLE`. Charts may be cleared or frozen. Slider changes do **not** advance the simulation. |
| **LIVE** | Simulation is running. Timesteps advance automatically. Slider changes take effect on the next tick. Charts and metrics update in real time. |
| **STOPPED** | Simulation is paused mid-run. Last computed values remain on screen. Slider changes do **not** advance the simulation until RUN is pressed again. |

### Button behaviour

| Button | Action |
|--------|--------|
| **RUN** | 1. Reset all input sliders/toggles to their **default values** (see inputs table). 2. Reset the simulation session (timestep counter, Kalman tracker, state machine, history). 3. Enter **LIVE** mode — simulation begins advancing automatically. |
| **STOP** | Pause the simulation. Exit **LIVE** mode and enter **STOPPED** mode. Preserve current slider values and last computed chart/metric values on screen. |
| **RESET** | Halt the simulation entirely. Enter **IDLE** mode. Force JIT system state to `IDLE`. Clear simulation history and charts. Slider values are **not** changed — only the simulation session and system state are reset. |

### Live mode mechanics

- `streamlit-autorefresh` triggers a Streamlit rerun at a fixed interval (recommended: 100–200 ms) **only while in LIVE mode**.
- On each tick, `app.py` calls a single-step advance function in `jit_core.py` (see `SimulationSession.step()` below).
- When the user moves a slider during LIVE mode, Streamlit reruns immediately; the new input values are picked up on the next tick.
- Use a **fixed random seed** per simulation session so Kalman noise does not flicker between reruns.
- When not in LIVE mode (IDLE or STOPPED), autorefresh is disabled — no timesteps advance.

---

## SIMULATION INPUTS

All inputs come from Streamlit sidebar sliders/toggles. No hardcoded values in logic. Defaults are used when RUN is pressed.

| Input | Type | Range | Default |
|-------|------|-------|---------|
| Vehicle speed | Slider | 40–120 km/h | 80 |
| Initial distance to obstacle | Slider | 10–100 m | 50 |
| Obstacle closing speed | Slider | 0–20 m/s | 10 |
| Road friction μ | Slider | 0.2–0.8 | 0.6 |
| Rain detected | Toggle | True/False | False |
| Camera confidence | Slider | 0.0–1.0 | 0.8 |
| Driver override | Toggle | True/False | False |

## SIMULATION OUTPUTS

| Output | Type | Location |
|--------|------|----------|
| System state | Status card | Top of main panel |
| TTC actual | Status card | Top of main panel |
| TTC minimum | Status card | Top of main panel |
| Warning stage | Status card | Top of main panel |
| Distance over time | Plotly line chart | Main panel row 2 left |
| TTC actual vs TTC min | Plotly line chart | Main panel row 2 right |
| Brake engagement (0–30%) | Progress bar | Main panel row 3 left |
| State timeline | Horizontal bar chart | Main panel row 3 right |

---

## CORE LOGIC — WHAT `jit_core.py` MUST CONTAIN

### 1. KalmanTracker class

- Uses `filterpy.kalman.KalmanFilter`
- State vector: `[distance, closing_velocity]`
- Input: noisy distance reading each timestep
- Output: smoothed distance + estimated closing velocity
- Purpose: models what the radar sensor output would look like after filtering

### 2. `calculate_ttc_actual(distance, closing_velocity)`

- Returns: `distance / closing_velocity`
- Guard: return infinity if `closing_velocity ≤ 0` (not closing)

### 3. `calculate_ttc_min(speed_ms, friction, t_actuation=0.3)`

- Formula: `speed_ms / (friction * 9.8) + t_actuation`
- `t_actuation` default: 0.3 seconds (300ms provisional — not yet measured on hardware)
- Returns: minimum seconds needed to stop safely

### 4. FrictionEstimator class

Three layers in priority order:

1. Layer 1: IMU value if available (passed in directly)
2. Layer 2: If `rain=True` and no IMU reading, return 0.4
3. Layer 3: Default fallback μ = 0.5

In simulation, IMU layer is bypassed — friction comes from slider directly. Class exists to mirror the real architecture even in simulation.

### 5. JITStateMachine class

Six states: `IDLE`, `THREAT_CANDIDATE`, `SUPPRESSED`, `ACTUATING`, `OVERRIDDEN`, `DEGRADED_CAMERA`

Transitions:

- `IDLE` → `THREAT_CANDIDATE`: when `TTC_actual ≤ TTC_min`
- `THREAT_CANDIDATE` → `ACTUATING`: when camera confidence ≥ threshold (default 0.6)
- `THREAT_CANDIDATE` → `SUPPRESSED`: when camera confidence < threshold
- `SUPPRESSED` → `IDLE`: after 1 second
- `ACTUATING` → `OVERRIDDEN`: when `driver_override = True` (toggle in UI)
- Any state → `DEGRADED_CAMERA`: when camera confidence < 0.2 for 3+ consecutive seconds
- `DEGRADED_CAMERA` brake rule: fire if `TTC_actual < TTC_min × 0.6` (radar-only fallback)

State machine tracks: current state, time in state, state history for timeline chart.

When UI mode is **IDLE** (RESET pressed), the state machine is forcibly set to `IDLE` regardless of TTC values.

### 6. `SimulationSession` class

Maintains live simulation state across ticks. Required for live mode.

Responsibilities:

- Hold current timestep, elapsed time, and rolling history arrays
- Own instances of `KalmanTracker`, `JITStateMachine`, and true obstacle distance
- Expose `reset(inputs)` — initialise a fresh session from input dict
- Expose `step(inputs, dt)` — advance one timestep, append to history, return current snapshot
- Expose `force_idle()` — halt logic and set state machine to `IDLE` (called on RESET)
- Use a fixed RNG seed per session for stable Kalman noise

Returns per tick: current distance, TTC_actual, TTC_min, state, brake_engagement, and full history arrays for charting.

### 7. `simulate_run(inputs)` function

- Batch helper: runs N timesteps in one call (default 100 steps)
- Used for testing and quick offline validation
- **Not** the primary path for the live dashboard — `SimulationSession` is
- Returns: arrays of distance, TTC_actual, TTC_min, state_at_each_step, brake_engagement

---

## UI LAYOUT — WHAT `app.py` MUST CONTAIN

### Sidebar (`st.sidebar`)

- All sliders and toggles as described in inputs table above
- Disabled camera button with caption: "Feature coming in hardware phase"
- **RUN** button (primary) — defaults + start live simulation
- **STOP** button — pause simulation, preserve display
- **RESET** button — halt simulation, force system to IDLE, clear charts

### Main panel

- **Row 1:** Four status cards — State, TTC Actual, TTC Min, Warning Stage
- **Row 2:** Two Plotly charts side by side using `st.columns(2)`
  - Left: Distance over time (grows live as ticks advance)
  - Right: TTC actual vs TTC min — TTC_min as a horizontal red line, TTC_actual as a blue falling line
- **Row 3:** Two outputs side by side using `st.columns(2)`
  - Left: `st.progress()` for brake engagement (0.0 to 0.3 max)
  - Right: Plotly horizontal bar chart for state timeline

### Color coding for state cards

| State | Color |
|-------|-------|
| IDLE | green |
| THREAT_CANDIDATE | orange |
| ACTUATING | red |
| SUPPRESSED | grey |
| OVERRIDDEN | blue |
| DEGRADED_CAMERA | yellow |

### Session state keys (Streamlit `st.session_state`)

| Key | Purpose |
|-----|---------|
| `ui_mode` | One of `"idle"`, `"live"`, `"stopped"` |
| `session` | `SimulationSession` instance (or `None` when idle) |
| `history` | Accumulated arrays for live chart rendering |

---

## IMPORTANT CONSTRAINTS — READ THESE

1. `t_actuation = 0.3` is provisional. It is a placeholder. Do not hardcode it anywhere except as a named constant at the top of `jit_core.py`. When the hardware team measures it, one line changes.
2. The camera confidence slider is a simulation proxy. In the real system this comes from an object detection model. Do not build any CV logic into this simulation.
3. The friction slider is a simulation proxy. In the real system this comes from the IMU + rain sensor three-layer estimator. The `FrictionEstimator` class must exist in the code even though the simulation bypasses Layer 1 — it mirrors the real architecture.
4. **Live mode is the primary operating mode.** Charts and metrics must update in real time while LIVE. Slider changes during LIVE take effect on the next tick without requiring a button press.
5. Autorefresh (`streamlit-autorefresh`) drives timestep advancement in LIVE mode only. Do not use infinite loops. Autorefresh must be disabled in IDLE and STOPPED modes.
6. All units internally are SI: metres, metres per second, seconds. Convert km/h to m/s on input before passing to any logic function.
7. The brake engagement output maxes at 0.3 (30% pedal travel). Never exceed this in the simulation output.
8. Use a fixed RNG seed per `SimulationSession` so chart lines do not jitter on every Streamlit rerun.

---

## WHAT IS DELIBERATELY LEFT OUT

- No real camera feed (placeholder button only)
- No hardware interface
- No GPS or real vehicle speed
- No actual radar data
- No drAIva AI layer (future phase — do not build)
- No user accounts or data persistence
- No mobile layout optimisation

---

## CONTEXT FOR SYSTEM DECISIONS

If you are confused about why a decision was made, the reasoning is:

- Radar replaced ultrasonic because ultrasonic fails in rain and darkness — common on Nigerian roads
- Camera is validation only, not primary sensing — prevents false braking
- Confidence gate exists because radar alone cannot classify objects
- Degraded camera fallback exists because rain + darkness make camera unreliable precisely when roads are most dangerous
- Upper 30% pedal zone is intentional — driver can always override by pressing normally
- `t_actuation` is provisional — not yet measured on actual hardware

---

## COMPETITION CONTEXT

This simulation will be demoed live to COUCH 2025 judges. The demo flow is:

1. Press **RESET** to show the system in IDLE (green, no threat)
2. Press **RUN** — sliders snap to defaults, simulation starts live
3. Drag speed up and friction down while live — TTC lines move in real time on the chart
4. Lower camera confidence below 0.6 — show state machine moving to SUPPRESSED or DEGRADED_CAMERA
5. Show brake engagement rising when ACTUATING fires
6. Press **STOP** to freeze the display and talk through what happened
7. Explain degraded camera fallback firing despite low confidence
8. Point to disabled camera button — explain hardware phase is next
