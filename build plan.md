=====================================================================================
MILESTONE 2 PROGRESS REPORT

Current progress:
- We have the Streamlit app running with a live `SimulationSession` backed by `JIT_core.py`.
- The app now supports a persistent session state across ticks and has distinct `idle`, `live`, and `stopped` modes.
- We've corrected early warning timing and added brake deceleration behavior so TTC responds correctly after actuation.

Bugs faced and fixed:
1. `st.session_state` modification after widget creation
   - Issue: `app.py` attempted to set widget-backed keys after sliders were instantiated, which Streamlit rejects.
   - Fix: removed those assignments and use current sidebar widget values directly when `RUN` is pressed.

2. Too-short warning window
   - Issue: the state machine transitioned from `IDLE` to `THREAT_CANDIDATE` only at `ttc_actual <= ttc_min`.
   - Fix: moved warning activation earlier to `ttc_actual <= ttc_min * 2` while preserving the `ACTUATING` threshold at `ttc_actual <= ttc_min`.

3. `ttc_actual` kept decreasing after actuation
   - Issue: actuation did not reduce closing speed, so the object continued closing at the same rate.
   - Fix: introduced brake deceleration so `closing_speed` falls when brakes are engaged.

4. Live simulation state and UI mode handling needed clarification
   - Issue: the app was not clearly structured for live tick-by-tick state persistence.
   - Fix: confirmed `SimulationSession` owns the tracker, state machine, elapsed time, and history arrays, while `app.py` maintains the UI mode and last snapshot.

Key changes made:
- Added `SimulationSession` behavior in `JIT_core.py` for live, incremental simulation.
- Updated `app.py` to control `RUN`, `STOP`, and `RESET` without invalid `session_state` mutations.
- Made `st_autorefresh` conditional on `live` mode.
- Extended warning state timing and added brake deceleration to the core physics logic.

What still remains:
- Verify the UI render path fully displays session histories and live updates correctly.
- Add unit tests for `simulate_run()` and `SimulationSession`.
- Pin dependencies in `requirements.txt` and include `streamlit-autorefresh`.
- Add a concise `README.md` with setup and run instructions.
- Perform a manual E2E check for `idle`, `live`, and `stopped` behavior.

Short checklist:
- [x] Fix Streamlit widget-state bug
- [x] Extend warning threshold to `ttc_min * 2`
- [x] Add brake deceleration once actuating
- [x] Keep live session state in `SimulationSession`
- [ ] Add unit tests
- [ ] Pin dependencies
- [ ] Add README
- [ ] Manual E2E validation

Next action:
- Implement unit tests and dependency pinning to lock in the current working design.

---

NOTE:
The current implementation now behaves more like a live automotive warning system: warnings start earlier, actuation still respects the minimum safe TTC, and braking changes the closing speed instead of letting the object close at constant velocity.

=====================================================================================
BUILD PLAN — AGREED SINGLE PLAN
=====================================================================================
=====================================================================================
BUILD PLAN — AGREED SINGLE PLAN

Purpose: establish a single, prioritized plan that any developer or automation (AI) can follow
to finish the JIT Simulation demo and prepare for the COUCH 2025 presentation.

Phases (high-level)
- Phase 1 — Core wiring (current priority): Wire the Streamlit UI to use `SimulationSession` so
	the app supports LIVE mode and sliders update charts on the next tick.
- Phase 2 — Environment & tests: pin dependencies in `requirements.txt` and add unit tests for
	`simulate_run()` and `SimulationSession` basics.
- Phase 3 — Demo materials: populate `build plan.md` (this file) with run and demo checklist,
	create a minimal `README.md` with run commands, and produce fallback static traces.
- Phase 4 — Polish & QA: address Kalman warm-up UX, color/label polish, and fix any small
	bugs discovered during manual E2E tests.
- Phase 5 — Demo prep: finalize script, produce backup datasets, and rehearse the demo.

Concrete next steps (actionable, ordered)
1. Wire `app.py` to `SimulationSession` (LIVE mode):
	 - On RUN: reset sliders to defaults, create `SimulationSession`, call `session.reset(inputs, seed)`
	 - While `ui_mode == 'live'`: enable `streamlit_autorefresh` (100–200 ms) and on each tick call
		 `snapshot = session.step(inputs)` and render `snapshot` histories for charts.
	 - STOP should pause `ui_mode` to `'stopped'` (autorefresh disabled) and preserve `session`.
	 - RESET should call `session.force_idle()` (or set `session = None`) and clear histories.

2. Update `requirements.txt`: ensure at minimum these packages are listed:
	 - `streamlit`
	 - `plotly`
	 - `filterpy`
	 - `numpy`
	 - `streamlit-autorefresh`

3. Add unit tests (suggested tests):
	 - `test_simulate_run.py`: call `simulate_run(_default_test_inputs())`, assert output array lengths
		 equal `DEFAULT_STEPS` and basic numeric invariants (non-negative distances, ttc_min finite).
	 - `test_simulation_session.py`: create a `SimulationSession`, `reset()` with defaults, call
		 `step()` multiple times and assert histories grow and state transitions occur.

4. Populate demo checklist and README:
	 - `build plan.md` (this file): include demo flow and expected judge interactions.
	 - `README.md`: include quick setup and run commands.

5. Manual E2E verification:
	 - Run the app locally and verify sliders change charts during LIVE runs.
	 - Validate three UI modes behave as documented.

Commands for local dev/test (copyable):
```bash
# create venv (optional)
python -m venv .venv
source .venv/Scripts/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# run unit tests
pytest -q

# run the Streamlit app
streamlit run app.py
```

Notes for other AIs or automation:
- Key files and symbols:
	- `JIT_core.py`: contains `SimulationSession`, `simulate_run()`, `KalmanTracker`, `JITStateMachine`.
	- `app.py`: Streamlit entry point (must remain UI-only); automation should modify `app.py`
		only to call `SimulationSession` APIs, not to duplicate logic.
	- `requirements.txt`: package manifest; keep minimal pinned versions if possible.
- Determinism: use a fixed RNG seed per `SimulationSession.reset(..., seed=...)` so charts don't jitter
	between Streamlit reruns.
- Live behaviour: sliders update internal session state on the next tick; do not recompute full
	traces on every Streamlit rerun — append a single-step snapshot instead.

Prioritized todo (short):
- Wire `app.py` → `SimulationSession` (in-progress)
- Add/verify `requirements.txt`
- Add unit tests
- Manual E2E test and polish

If you want, I can now implement the `app.py` wiring to `SimulationSession` and add a minimal
`requirements.txt` entry and unit tests. Which of those should I start next?
