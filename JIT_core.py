"""JIT simulation core logic — no UI code."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
from filterpy.kalman import KalmanFilter

T_ACTUATION = 0.3
CAMERA_CONFIDENCE_THRESHOLD = 0.6
DEGRADED_CAMERA_THRESHOLD = 0.2
DEGRADED_CAMERA_SECONDS = 3.0
SUPPRESSED_TO_IDLE_SECONDS = 1.0
BRAKE_MAX = 0.3
BRAKE_DECELERATION = 5.0
GRAVITY = 9.8
DEFAULT_STEPS = 100
DEFAULT_DT = 0.1
DISTANCE_NOISE_STD = 1.5


class JITState(str, Enum):
    IDLE = "IDLE"
    THREAT_CANDIDATE = "THREAT_CANDIDATE"
    SUPPRESSED = "SUPPRESSED"
    ACTUATING = "ACTUATING"
    OVERRIDDEN = "OVERRIDDEN"
    DEGRADED_CAMERA = "DEGRADED_CAMERA"


class KalmanTracker:
    """Smooth noisy distance readings and estimate closing velocity."""

    def __init__(self, dt: float = DEFAULT_DT) -> None:
        self.dt = dt
        self.kf = KalmanFilter(dim_x=2, dim_z=1)
        self.kf.F = np.array([[1.0, dt], [0.0, 1.0]])
        self.kf.H = np.array([[1.0, 0.0]])
        self.kf.R = np.array([[DISTANCE_NOISE_STD**2]])
        self.kf.Q = np.array([[0.1, 0.0], [0.0, 0.5]])
        self.kf.P *= 10.0
        self._initialized = False

    def reset(self, initial_distance: float) -> None:
        self.kf.x = np.array([[initial_distance], [0.0]])
        self._initialized = False

    def update(self, noisy_distance: float) -> tuple[float, float]:
        if not self._initialized:
            self.kf.x[0, 0] = noisy_distance
            self._initialized = True
        self.kf.predict()
        self.kf.update(np.array([[noisy_distance]]))
        distance = float(self.kf.x[0, 0])
        closing_velocity = float(max(self.kf.x[1, 0], 0.0))
        return distance, closing_velocity


def calculate_ttc_actual(distance: float, closing_velocity: float) -> float:
    if closing_velocity <= 0:
        return float("inf")
    return distance / closing_velocity


def calculate_ttc_min(
    speed_ms: float,
    friction: float,
    t_actuation: float = T_ACTUATION,
) -> float:
    if friction <= 0 or speed_ms <= 0:
        return float("inf")
    return speed_ms / (friction * GRAVITY) + t_actuation


class FrictionEstimator:
    """Three-layer friction estimate mirroring the real JIT architecture."""

    RAIN_FRICTION = 0.4
    DEFAULT_FRICTION = 0.5

    def estimate(
        self,
        *,
        imu_value: float | None = None,
        rain: bool = False,
    ) -> float:
        if imu_value is not None:
            return imu_value
        if rain:
            return self.RAIN_FRICTION
        return self.DEFAULT_FRICTION


@dataclass
class JITStateMachine:
    state: JITState = JITState.IDLE
    time_in_state: float = 0.0
    low_confidence_duration: float = 0.0
    history: list[tuple[float, JITState]] = field(default_factory=list)

    def reset(self) -> None:
        self.state = JITState.IDLE
        self.time_in_state = 0.0
        self.low_confidence_duration = 0.0
        self.history = []

    def force_idle(self) -> None:
        self.state = JITState.IDLE
        self.time_in_state = 0.0
        self.low_confidence_duration = 0.0

    def step(
        self,
        dt: float,
        ttc_actual: float,
        ttc_min: float,
        camera_confidence: float,
        driver_override: bool,
    ) -> JITState:
        if camera_confidence < DEGRADED_CAMERA_THRESHOLD:
            self.low_confidence_duration += dt
        else:
            self.low_confidence_duration = 0.0

        if (
            self.low_confidence_duration >= DEGRADED_CAMERA_SECONDS
            and self.state != JITState.OVERRIDDEN
        ):
            self._transition(JITState.DEGRADED_CAMERA, dt)
        elif self.state == JITState.IDLE:
            if ttc_actual <= ttc_min * 2:
                self._transition(JITState.THREAT_CANDIDATE, dt)
            else:
                self.time_in_state += dt
        elif self.state == JITState.THREAT_CANDIDATE:
            if camera_confidence >= CAMERA_CONFIDENCE_THRESHOLD:
                if ttc_actual <= ttc_min:
                    self._transition(JITState.ACTUATING, dt)
                else:
                    self.time_in_state += dt
            else:
                self._transition(JITState.SUPPRESSED, dt)
        elif self.state == JITState.SUPPRESSED:
            self.time_in_state += dt
            if self.time_in_state >= SUPPRESSED_TO_IDLE_SECONDS:
                self._transition(JITState.IDLE, dt)
        elif self.state == JITState.ACTUATING:
            self.time_in_state += dt
            if driver_override:
                self._transition(JITState.OVERRIDDEN, dt)
        elif self.state == JITState.DEGRADED_CAMERA:
            self.time_in_state += dt
        elif self.state == JITState.OVERRIDDEN:
            self.time_in_state += dt

        return self.state

    def _transition(self, new_state: JITState, dt: float) -> None:
        if new_state != self.state:
            self.state = new_state
            self.time_in_state = 0.0
        else:
            self.time_in_state += dt

    def record(self, elapsed: float) -> None:
        self.history.append((elapsed, self.state))


def should_engage_brake(
    state: JITState,
    ttc_actual: float,
    ttc_min: float,
) -> bool:
    if state == JITState.ACTUATING:
        return True
    if state == JITState.DEGRADED_CAMERA and ttc_actual < ttc_min * 0.6:
        return True
    return False


def kmh_to_ms(speed_kmh: float) -> float:
    return speed_kmh / 3.6


def simulate_run(
    inputs: dict[str, Any],
    n_steps: int = DEFAULT_STEPS,
    dt: float = DEFAULT_DT,
    rng: np.random.Generator | None = None,
) -> dict[str, Any]:
    """Run the full JIT pipeline across N timesteps and return output arrays."""
    if rng is None:
        rng = np.random.default_rng(42)

    speed_ms = kmh_to_ms(float(inputs["vehicle_speed_kmh"]))
    initial_distance = float(inputs["initial_distance_m"])
    closing_speed = float(inputs["obstacle_closing_speed_ms"])
    friction_slider = float(inputs["road_friction"])
    rain = bool(inputs.get("rain_detected", False))
    camera_confidence = float(inputs["camera_confidence"])
    driver_override = bool(inputs.get("driver_override", False))

    friction = FrictionEstimator().estimate(imu_value=friction_slider, rain=rain)
    ttc_min = calculate_ttc_min(speed_ms, friction)

    tracker = KalmanTracker(dt=dt)
    tracker.reset(initial_distance)
    state_machine = JITStateMachine()

    times = np.zeros(n_steps)
    distances = np.zeros(n_steps)
    ttc_actuals = np.zeros(n_steps)
    ttc_mins = np.full(n_steps, ttc_min)
    states: list[JITState] = []
    brake_engagement = np.zeros(n_steps)

    true_distance = initial_distance
    brake_level = 0.0
    ramp_rate = BRAKE_MAX / 1.0

    for i in range(n_steps):
        elapsed = i * dt
        times[i] = elapsed

        noisy_distance = true_distance + rng.normal(0.0, DISTANCE_NOISE_STD)
        noisy_distance = max(noisy_distance, 0.0)
        distance, _ = tracker.update(noisy_distance)

        ttc_actual = calculate_ttc_actual(distance, closing_speed)
        distances[i] = distance
        ttc_actuals[i] = ttc_actual

        current_state = state_machine.step(
            dt=dt,
            ttc_actual=ttc_actual,
            ttc_min=ttc_min,
            camera_confidence=camera_confidence,
            driver_override=driver_override,
        )
        state_machine.record(elapsed)
        states.append(current_state)

        if should_engage_brake(current_state, ttc_actual, ttc_min):
            brake_level = min(brake_level + ramp_rate * dt, BRAKE_MAX)
        else:
            brake_level = max(brake_level - ramp_rate * dt, 0.0)

        closing_speed = max(closing_speed - brake_level * BRAKE_DECELERATION * dt, 0.0)
        if closing_speed > 0:
            true_distance = max(true_distance - closing_speed * dt, 0.0)

        brake_engagement[i] = brake_level

    return {
        "times": times,
        "distances": distances,
        "ttc_actuals": ttc_actuals,
        "ttc_mins": ttc_mins,
        "states": states,
        "state_history": state_machine.history,
        "brake_engagement": brake_engagement,
        "friction_used": friction,
        "ttc_min": ttc_min,
    }


@dataclass
class SimulationSession:
    """Maintain live simulation state across ticks for Streamlit UI.

    Usage:
      session = SimulationSession(dt=0.1)
      session.reset(inputs, seed=42)
      snapshot = session.step(inputs)
    """

    dt: float = DEFAULT_DT
    seed: int = 42

    # runtime fields
    rng: np.random.Generator = field(init=False)
    tracker: KalmanTracker = field(init=False)
    state_machine: JITStateMachine = field(init=False)
    elapsed: float = 0.0
    true_distance: float = 0.0
    brake_level: float = 0.0
    ramp_rate: float = BRAKE_MAX / 1.0

    # history for charts
    times: list[float] = field(default_factory=list)
    distances: list[float] = field(default_factory=list)
    ttc_actuals: list[float] = field(default_factory=list)
    ttc_mins: list[float] = field(default_factory=list)
    states: list[JITState] = field(default_factory=list)
    brake_engagement: list[float] = field(default_factory=list)

    # current inputs snapshot (useful for repeatable behaviour)
    speed_ms: float = 0.0
    closing_speed: float = 0.0
    friction_used: float = 0.0

    def reset(self, inputs: dict[str, Any], seed: int | None = None) -> None:
        if seed is None:
            seed = self.seed
        self.rng = np.random.default_rng(seed)

        self.dt = float(self.dt)
        self.speed_ms = kmh_to_ms(float(inputs.get("vehicle_speed_kmh", 0)))
        initial_distance = float(inputs.get("initial_distance_m", 0))
        self.closing_speed = float(inputs.get("obstacle_closing_speed_ms", 0))
        friction_slider = float(inputs.get("road_friction", 0.5))
        rain = bool(inputs.get("rain_detected", False))

        self.friction_used = FrictionEstimator().estimate(imu_value=friction_slider, rain=rain)

        # initialise stateful components
        self.tracker = KalmanTracker(dt=self.dt)
        self.tracker.reset(initial_distance)
        self.state_machine = JITStateMachine()

        # reset runtime values and histories
        self.elapsed = 0.0
        self.true_distance = float(initial_distance)
        self.brake_level = 0.0
        self.times.clear()
        self.distances.clear()
        self.ttc_actuals.clear()
        self.ttc_mins.clear()
        self.states.clear()
        self.brake_engagement.clear()

    def force_idle(self) -> None:
        self.state_machine.force_idle()

    def step(self, inputs: dict[str, Any], dt: float | None = None) -> dict[str, Any]:
        """Advance a single timestep using the provided inputs and return a snapshot."""
        if dt is None:
            dt = self.dt
        else:
            dt = float(dt)

        # read inputs that can change live
        camera_confidence = float(inputs.get("camera_confidence", 0.0))
        driver_override = bool(inputs.get("driver_override", False))
        rain = bool(inputs.get("rain_detected", False))
        friction_slider = float(inputs.get("road_friction", self.friction_used if self.friction_used else 0.5))
        self.speed_ms = kmh_to_ms(float(inputs.get("vehicle_speed_kmh", self.speed_ms)))
        self.closing_speed = float(inputs.get("obstacle_closing_speed_ms", self.closing_speed))

        # recompute friction and ttc_min each tick (slider may change)
        self.friction_used = FrictionEstimator().estimate(imu_value=friction_slider, rain=rain)
        ttc_min = calculate_ttc_min(self.speed_ms, self.friction_used)

        # sensor reading with noise
        noisy_distance = self.true_distance + self.rng.normal(0.0, DISTANCE_NOISE_STD)
        noisy_distance = max(noisy_distance, 0.0)
        distance, _ = self.tracker.update(noisy_distance)

        # advance true object position
        if self.closing_speed > 0:
            self.true_distance = max(self.true_distance - self.closing_speed * dt, 0.0)

        ttc_actual = calculate_ttc_actual(distance, self.closing_speed)

        # update state machine
        current_state = self.state_machine.step(
            dt=dt,
            ttc_actual=ttc_actual,
            ttc_min=ttc_min,
            camera_confidence=camera_confidence,
            driver_override=driver_override,
        )
        self.state_machine.record(self.elapsed)

        # brake engagement ramp
        if should_engage_brake(current_state, ttc_actual, ttc_min):
            self.brake_level = min(self.brake_level + self.ramp_rate * dt, BRAKE_MAX)
        else:
            self.brake_level = max(self.brake_level - self.ramp_rate * dt, 0.0)

        self.closing_speed = max(self.closing_speed - self.brake_level * BRAKE_DECELERATION * dt, 0.0)
        if self.closing_speed > 0:
            self.true_distance = max(self.true_distance - self.closing_speed * dt, 0.0)

        # append histories
        self.times.append(self.elapsed)
        self.distances.append(distance)
        self.ttc_actuals.append(ttc_actual)
        self.ttc_mins.append(ttc_min)
        self.states.append(current_state)
        self.brake_engagement.append(self.brake_level)

        snapshot = {
            "time": self.elapsed,
            "distance": distance,
            "ttc_actual": ttc_actual,
            "ttc_min": ttc_min,
            "state": current_state,
            "brake_level": self.brake_level,
            "times": list(self.times),
            "distances": list(self.distances),
            "ttc_actuals": list(self.ttc_actuals),
            "ttc_mins": list(self.ttc_mins),
            "states": list(self.states),
            "brake_engagement": list(self.brake_engagement),
            "friction_used": self.friction_used,
        }

        # advance time
        self.elapsed += dt

        return snapshot


def _default_test_inputs() -> dict[str, Any]:
    return {
        "vehicle_speed_kmh": 80,
        "initial_distance_m": 50,
        "obstacle_closing_speed_ms": 10,
        "road_friction": 0.6,
        "rain_detected": False,
        "camera_confidence": 0.8,
        "driver_override": False,
    }


if __name__ == "__main__":
    result = simulate_run(_default_test_inputs())

    print("JIT Core — simulate_run() test")
    print("-" * 40)
    print(f"Friction used:     {result['friction_used']:.2f}")
    print(f"TTC minimum:       {result['ttc_min']:.3f} s")
    print(f"Final distance:    {result['distances'][-1]:.2f} m")
    print(f"Final TTC actual:  {result['ttc_actuals'][-1]:.3f} s")
    print(f"Final state:       {result['states'][-1].value}")
    print(f"Final brake level: {result['brake_engagement'][-1]:.3f}")
    print()
    print("Output array lengths (expected 100):")
    for key in ("times", "distances", "ttc_actuals", "ttc_mins", "brake_engagement"):
        print(f"  {key}: {len(result[key])}")
    print(f"  states: {len(result['states'])}")
    print(f"  state_history: {len(result['state_history'])}")
    print()
    print("State sequence (first 10 steps):")
    for t, state in result["state_history"][:10]:
        print(f"  t={t:4.1f}s  {state.value}")
