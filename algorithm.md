# JIT CORE

## Purpose

JIT CORE is the pure-Python decision engine for the JIT (Just In Time) Automatic Emergency Braking simulation. It contains no Streamlit, dashboard, or hardware code. Its job is to turn simulated sensor inputs into a safe braking decision and a history that the user interface can display.

The pipeline is:

```text
Simulated radar distance
        -> Kalman smoothing
        -> collision-risk calculation (TTC)
        -> JIT safety state machine
        -> limited brake command (0% to 30%)
        -> chart/history snapshot
```

All internal values use SI units: metres, metres per second, and seconds. Dashboard speed in km/h is converted before calculations.

---

## Inputs and outputs

### Inputs

| Input | Meaning |
|---|---|
| Vehicle speed | Vehicle speed in km/h; converted to m/s. |
| Initial distance | Starting distance to the obstacle, in metres. |
| Closing speed | How fast the obstacle distance is reducing, in m/s. |
| Road friction | Road grip value (mu), supplied by the simulation slider. |
| Rain detected | Fallback input for the friction estimator. |
| Camera confidence | Confidence from 0.0 to 1.0 used to validate a threat. |
| Driver override | Indicates that the driver has taken control. |

### Outputs per simulation tick

| Output | Meaning |
|---|---|
| Smoothed distance | Kalman-filtered radar distance. |
| TTC actual | Estimated seconds until impact. |
| TTC minimum | Seconds needed to stop safely. |
| State | Current JIT safety state. |
| Brake level | Brake command from 0.0 to 0.3 only. |
| History arrays | Values used by the live dashboard charts. |

---

## Main calculations

### 1. Convert speed

```text
speed_m/s = speed_km/h / 3.6
```

### 2. Calculate actual Time To Collision (TTC)

```text
TTC actual = distance / closing speed
```

If the closing speed is zero or negative, the object is not approaching, so TTC is infinity.

### 3. Calculate the minimum safe TTC

```text
TTC minimum = vehicle speed / (road friction * 9.8) + actuator delay
```

The actuator delay is a named constant, currently `T_ACTUATION = 0.3` seconds. This value is provisional until hardware testing measures the real brake-actuator delay.

### Example

```text
Vehicle speed: 80 km/h = 22.22 m/s
Road friction: 0.6
TTC minimum: 22.22 / (0.6 * 9.8) + 0.3 = about 4.08 s
```

If the obstacle is 20 m away and closing speed is 10 m/s:

```text
TTC actual = 20 / 10 = 2 s
```

Since 2 s is below 4.08 s, the system identifies a possible threat.

---

## Build order

Build and test JIT CORE in this order:

1. Define named constants, such as gravity, confidence thresholds, and the 30% brake limit.
2. Define the six `JITState` values.
3. Add unit conversion and TTC calculation functions.
4. Add `FrictionEstimator` with its real-system fallback architecture.
5. Add `KalmanTracker` to smooth noisy simulated radar readings.
6. Add `JITStateMachine` and its state transitions.
7. Add the brake-engagement rule and gradual brake ramp.
8. Create `simulate_run()` for batch testing.
9. Create `SimulationSession` for one live tick at a time.
10. Let `app.py` call `SimulationSession`; keep all decision logic in `JIT_core.py`.

---

## Sensor smoothing: Kalman tracker

Radar readings are imperfect. The Kalman tracker receives a noisy distance measurement and produces a smoother estimate suitable for charts and decisions.

```text
Noisy distance reading
        -> predict where the obstacle should be
        -> compare prediction with new reading
        -> correct the estimate
        -> smoothed distance
```

The filter tracks two values:

```text
[distance, estimated closing velocity]
```

The simulation adds controlled random noise with a fixed random seed. A fixed seed makes the same run repeatable instead of making the charts jump unpredictably after every Streamlit rerun.

---

## Friction estimator

The simulation currently passes the slider value as an IMU-like friction value, but the class mirrors the intended hardware architecture.

```text
IMU friction value available?
    Yes -> use it
    No  -> rain detected?
              Yes -> use 0.4
              No  -> use default 0.5
```

---

## JIT state machine

| State | Meaning |
|---|---|
| `IDLE` | No immediate collision threat. |
| `THREAT_CANDIDATE` | TTC indicates danger; camera validation is required. |
| `SUPPRESSED` | Threat was not validated by the camera. |
| `ACTUATING` | JIT is applying limited braking. |
| `OVERRIDDEN` | Driver has taken control. |
| `DEGRADED_CAMERA` | Camera has had very low confidence for at least 3 seconds. |

### Decision algorithm

```text
IF camera confidence is below 0.2:
    add dt to the low-confidence timer
ELSE:
    reset the low-confidence timer

IF low-confidence timer is at least 3 seconds:
    state = DEGRADED_CAMERA

ELSE IF state is IDLE AND TTC actual <= TTC minimum:
    state = THREAT_CANDIDATE

ELSE IF state is THREAT_CANDIDATE:
    IF camera confidence >= 0.6:
        state = ACTUATING
    ELSE:
        state = SUPPRESSED

ELSE IF state is SUPPRESSED for at least 1 second:
    state = IDLE

ELSE IF state is ACTUATING AND driver override is true:
    state = OVERRIDDEN
```

### State flowchart

```text
                           TTC actual <= TTC minimum
  [IDLE] ------------------------------------------------> [THREAT_CANDIDATE]
                                                               |          |
                                         camera >= 0.6         |          | camera < 0.6
                                                               v          v
                                                        [ACTUATING]  [SUPPRESSED]
                                                             |             |
                                              driver override |             | after 1 second
                                                             v             v
                                                       [OVERRIDDEN]     [IDLE]

  Camera confidence < 0.2 for 3+ seconds
  from normal operating states ---------------------------> [DEGRADED_CAMERA]
```

---

## Brake engagement rule

```text
ACTUATING state:
    engage brake

DEGRADED_CAMERA state:
    engage brake only when TTC actual < TTC minimum * 0.6

All other states:
    do not engage brake
```

The degraded-camera rule is stricter because JIT is operating without reliable camera validation.

Brake output is ramped rather than switched immediately:

```text
If braking is required:
    brake = minimum(brake + ramp_rate * dt, 0.3)
Otherwise:
    brake = maximum(brake - ramp_rate * dt, 0.0)
```

The simulation never commands more than `0.3`, representing 30% pedal travel.

---

## Live simulation tick

`SimulationSession.step(inputs)` completes one time step, normally `dt = 0.1` seconds.

```text
1. Read the latest slider and toggle values.
2. Convert vehicle speed to m/s.
3. Estimate road friction and calculate TTC minimum.
4. Add controlled noise to the true obstacle distance.
5. Smooth that radar reading with the Kalman tracker.
6. Move the simulated obstacle closer by closing_speed * dt.
7. Calculate TTC actual.
8. Advance the JIT state machine.
9. Decide whether braking is permitted.
10. Ramp the brake level up or down.
11. Save values to history and return a snapshot for the UI.
```

`SimulationSession.reset(inputs)` starts a clean, repeatable run. `force_idle()` is used by RESET to halt logic and force the state to `IDLE`.

---

## Testing sequence

Use `simulate_run(inputs)` before connecting the dashboard.

1. Normal conditions: confirm the state starts as `IDLE`.
2. Reduce distance or increase closing speed: confirm it reaches `THREAT_CANDIDATE`.
3. Set camera confidence to 0.8: confirm it reaches `ACTUATING` and brake rises toward 0.3.
4. Set camera confidence below 0.6: confirm it reaches `SUPPRESSED`.
5. Keep confidence below 0.2 for 3 seconds: confirm it reaches `DEGRADED_CAMERA`.
6. Enable driver override during `ACTUATING`: confirm it reaches `OVERRIDDEN`.
7. Confirm brake engagement never exceeds 0.3.
