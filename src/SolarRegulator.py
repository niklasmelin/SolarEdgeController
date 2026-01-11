from typing import Optional


class SolarRegulator:
    """
    Real-time solar inverter export regulator.

    This class computes an integer inverter scale factor (0–100%)
    to limit grid export to a configured maximum, using only current
    measurements and internal state.

    The regulator:
    - Operates in watts (not percent) to avoid overshoot
    - Uses proportional ramping for smooth small adjustments
    - Applies a hard safety limit on ramp speed
    - Is stable under fast solar ramps and noisy household load
    """

    def __init__(self) -> None:
        """
        Initialize the solar export regulator.

        Internal state is empty until the first call to `new_scale_factor`.
        """

        # ---------------- CONFIGURATION ----------------
        self.PEAK_PRODUCTION_W: float = 10500.0
        self.MIN_PRODUCTION_W: float = 300.0
        self.MAX_EXPORT_W: float = 200.0

        self.MAX_DELTA_PERCENT_PER_15S: float = 5.0
        self.DT: float = 10.0  # Controller period in seconds

        self.GAIN_SMALL_ERROR: float = 0.3
        self.LOW_PV_THRESHOLD: float = 50.0
        # ------------------------------------------------

        # Internal state
        self.last_limited_power: Optional[float] = None

        # Precomputed maximum power change per control cycle [W]
        self.max_step_watt: float = (
            self.MAX_DELTA_PERCENT_PER_15S / 100.0
            * self.PEAK_PRODUCTION_W
            * (self.DT / 15.0)
        )

    def new_scale_factor(self, current_home_consumption: float, current_solar_production: float) -> int:
        """
        Compute the next inverter scale factor.

        This method must be called once per control cycle.
        It updates internal state and returns a scale factor
        suitable for direct inverter control.

        Parameters
        ----------
        current_home_consumption : float
            Current household power consumption in watts.
            Negative values are treated as zero.

        current_solar_production : float
            Current inverter output power before limiting (watts).

        Returns
        -------
        int
            Integer inverter scale factor in the range 0–100 (%).
        """

        # Sanitize inputs
        home: float = max(0.0, float(current_home_consumption))
        solar: float = max(0.0, float(current_solar_production))

        # Initialize internal state on first call
        if self.last_limited_power is None:
            self.last_limited_power = solar

        # Night or very low PV → no regulation
        if solar < self.LOW_PV_THRESHOLD:
            self.last_limited_power = solar
            return 100

        # Target inverter output to meet export constraint
        desired_power: float = home + self.MAX_EXPORT_W

        # Control error (watts)
        error: float = desired_power - self.last_limited_power

        # Proportional step (gentle for small errors)
        step: float = error * self.GAIN_SMALL_ERROR

        # Hard ramp limit (safety)
        step = max(-self.max_step_watt, min(self.max_step_watt, step))

        # Apply step
        limited_power: float = self.last_limited_power + step

        # Physical constraints
        limited_power = max(limited_power, self.MIN_PRODUCTION_W)
        limited_power = min(limited_power, solar)

        # Update state
        self.last_limited_power = limited_power

        # Convert to integer scale factor
        scale_factor: int = int(round(100.0 * limited_power / solar))
        scale_factor = max(0, min(100, scale_factor))

        return scale_factor
