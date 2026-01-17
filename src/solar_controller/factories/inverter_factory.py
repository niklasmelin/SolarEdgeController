from solar_controller.inverter.solaredge_inverter import SolarEdgeInverter
from solar_controller.config import InverterConfig


def create_inverter(config: InverterConfig) -> SolarEdgeInverter:
    """
    Instantiate the configured inverter.
    """
    return SolarEdgeInverter(
        device=config.device,
        baud=config.baud,
        timeout=config.timeout,
    )
