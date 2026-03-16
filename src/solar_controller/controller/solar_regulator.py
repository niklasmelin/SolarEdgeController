import logging
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
        self.MIN_PRODUCTION_W: float = 500.0
        self.MAX_EXPORT_W: float = 200.0

        self.MAX_DELTA_PERCENT_PER_15S: float = 10.0
        # self.DT: float = 10.0  # Controller period in seconds

        self.GAIN_SMALL_ERROR: float = 0.3
        self.LOW_PV_THRESHOLD: float = 50.0
        # ------------------------------------------------

        # Internal state
        self.last_limited_power: Optional[float] = None        
        self.limit_export: bool = False
        self.auto_mode: bool = False
        self.auto_mode_threshold: float = 0.0
        self.power_limit: float = 0.0

        # Precomputed maximum power change per control cycle [W]
        #self.max_step_watt: float = (
        #    self.MAX_DELTA_PERCENT_PER_15S / 100.0
        #    * self.PEAK_PRODUCTION_W
        #    * (self.DT / 15.0)
        #)
        
        self.max_step_watt: float = (
            self.MAX_DELTA_PERCENT_PER_15S / 100.0
            * self.PEAK_PRODUCTION_W
        )
        

    def new_scale_factor(self,
                         current_grid_consumption: float,
                         current_solar_production: float,
                         limit_export: bool = False,
                         auto_mode: bool = False,
                         auto_mode_threshold: float = 0.0,
                         power_limit_W: float = 0.0) -> int:
        """
        Compute the next inverter scale factor.
        This method must be called once per control cycle.
        It updates internal state and returns a scale factor
        suitable for direct inverter control.

        Parameters
        ----------
        current_grid_consumption : float
        Current household power consumption in watts.
        Negative values are treated as zero.

        If limit_export is enablend the regulator will stear towards the following target:
            If auto_mode is enabled:
                Stear towards the power_limit value for export
            If auto_mode is disabled:
                Constant limited solar production according to the power_limit. I.e. the inverter will not produce more that this value.
        If limit_export is disabled.
            Inverter will produce as much as possible.

        auto_mode : bool
        Use automatic mode ( True ) or manual mode ( False )

        auto_mode_threshold : float
        Threshold value for auto mode

        power_limit : float
        Maximum power output of the solar panel

        Returns
        -------
        int
        Integer inverter scale factor in the range 0–100 (%).
        """

        logging.debug(f"Calculating new scale factor with grid consumption {current_grid_consumption} W, solar production {current_solar_production} W, limit_export {limit_export}, auto_mode {auto_mode}, auto_mode_threshold {auto_mode_threshold} W, power_limit {power_limit_W} W")

        # Sanitize inputs
        solar: float = max(0.0, float(current_solar_production))
        home: float = max(0.0, float(current_grid_consumption) + solar)  # Total household load (consumption + solar)
        
        # Initialize internal state on first call
        if self.last_limited_power is None:
            self.last_limited_power = solar

        # Night or very low PV → no regulation
        if solar < self.LOW_PV_THRESHOLD:
            self.last_limited_power = solar
            logging.debug(f"Solar production {solar} W is below low PV threshold {self.LOW_PV_THRESHOLD} W, setting scale factor to 100%")
            
            # Clear export limit state when solar is very low to avoid erratic behavior when sun comes up
            self.last_limited_power = None
            
            return 100

        if not limit_export:
            # No export limit, run at full production
            logging.debug("Export limit disabled, setting scale factor to 100%")
            
            # Clear export limit state when solar is very low to avoid erratic behavior when sun comes up
            self.last_limited_power = None
            
            return 100
        
        else:
            # Export limit enabled, check auto mode
            if auto_mode:
                # Auto mode enabled, target inverter output to meet export constraint.
                desired_power: float = home + self.MAX_EXPORT_W
                
                # Control error (watts)
                error: float = desired_power - self.last_limited_power
                
                logging.debug(f"Auto mode enabled, Desired power {desired_power} W, Home {home} W + Max export {self.MAX_EXPORT_W} W, Error {error} W, Last limited power {self.last_limited_power} W")

                # Proportional step (gentle for small errors)
                step: float = error * self.GAIN_SMALL_ERROR

                # Hard ramp limit (safety)
                step = max(-self.max_step_watt, min(self.max_step_watt, step))
                logging.debug(f"Auto mode enabled Max step {self.max_step_watt} W, error {error} W, proportional step {step} W")


                # Apply step
                limited_power: float = self.last_limited_power + step

                # Physical constraints
                limited_power = max(limited_power, self.MIN_PRODUCTION_W) # Don't go below minimum production
                limited_power = min(limited_power, self.PEAK_PRODUCTION_W) # Don't exceed peak production   
                

                # Convert to integer scale factor
                scale_factor: int = int(round(100.0 * limited_power / self.PEAK_PRODUCTION_W))
                logging.debug(f"Auto mode enabled, limited power {limited_power} W, solar {solar} W, preliminary scale factor {scale_factor}%")
                scale_factor = max(0, min(100, scale_factor))

                logging.debug(f"Auto mode enabled and home consumption {home} W threshold {auto_mode_threshold} W, setting power limit to {scale_factor}% ({limited_power} W) with error {error} W and step {step} W")

            # Manual mode, target constant limited power output
            else:
                limited_power = power_limit_W
                logging.debug(f"Auto mode disabled, using power limit {power_limit_W} W")

                # Physical constraints
                if self.MIN_PRODUCTION_W <= power_limit_W <= self.PEAK_PRODUCTION_W:
                    scale_factor = int(round(100.0 * limited_power / self.PEAK_PRODUCTION_W))
                else:
                    logging.warning(f"Power limit {power_limit_W} W is out of bounds, setting scale factor to 100%")
                    scale_factor = 100

        # Update state
        self.last_limited_power = limited_power



        return scale_factor
