JIT — Just In Time
Retrofit AEB for Legacy Commercial Vehicles
By Team Axora

What is JIT?
JIT (Just In Time) is an aftermarket Automatic Emergency Braking system designed to be installed on commercial vehicles already on the road — buses, trucks, and danfos — that were never built with active safety systems.
Nigeria loses tens of thousands of lives to road crashes every year. The vast majority are attributable to human error. The existing fleet cannot wait for a new-vehicle turnover cycle. JIT retrofits the solution onto the vehicles that are already out there.

How it works
JIT uses a 77GHz mmWave radar as its primary sensor, paired with a camera, IMU, and rain sensor, to calculate a dynamic Time-to-Collision threshold in real time. When a collision risk is detected, the system escalates through three intervention levels — Forward Collision Warning, Demand Braking Support, and Critical Intervention Braking — before physically actuating a lead screw mechanism against the brake pedal.
All safety-critical logic runs on an STM32 microcontroller. A secondary Qualcomm processor handles mid-range optical context at 30fps. The two communicate over a defined interface with explicit timeout and fallback rules.

Current status
This repository is focused on the JIT simulation demo.
- `app.py` is a Streamlit frontend driving a live `SimulationSession` from `JIT_core.py`.
- The app now supports `idle`, `live`, and `stopped` modes.
- Warning activation has been extended to `ttc_min * 2`, while braking now reduces the closing speed during actuation.

How to run
1. Create and activate a Python environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Launch the Streamlit app:
   ```bash
   streamlit run app.py
   ```

Expected behaviour
- Press `RUN` to start the live simulation.
- The app advances the simulation in realtime while `live` mode is active.
- Use `STOP` to pause and `RESET` to clear the session.
- Slider changes are applied on the next tick.

Repository structure
- `app.py` — Streamlit UI entry point
- `JIT_core.py` — simulation core logic, state machine, and live session handling
- `build plan.md` — progress report and development plan
- `requirements.txt` — Python dependencies

Team
Team Axora

Emmanuel — Project Lead
Abdulbasit — Technical Co-Lead
Dorcas - Intelligence and computing lead
Maryam - Research and Business Strategy 

Licence
(To be decided)
