from solar_controller.inverter.solaredge_inverter import SolarEdgeInverter

def create_inverter(config):
    """Simple Factory: instantiate the configured inverter."""
    return SolarEdgeInverter(
        device=config.SOLAR_EDGE_INVERTER_DEVICE,
        baud=config.SOLAR_EDGE_INVERTER_BAUD,
        timeout=config.SOLAR_EDGE_INVERTER_TIMEOUT,
    )
