# EspReader — ESPHome Async Sensor Reader

`EspReader` is an asynchronous Python class for **stable, continuous reading of ESPHome devices** using `aioesphomeapi`.

It is designed for:
- Long-lived connections
- Reliable first-read initialization
- Detection of stale vs fresh data
- Non-blocking, synchronous data access after connection
- Clear failure modes (no silent empty data)

---

## Key Features

- ✅ Persistent connection to ESPHome (no reconnect-per-read)
- ✅ Waits for **all entities** to report (with timeout)
- ✅ Per-sensor timestamps (`last_updated`)
- ✅ Detects missing or stale sensors
- ✅ Instant reads (`get_data_as_json()` is non-async)
- ✅ Safe API: raises error if used before connecting

---

## Class Overview

```python
class EspReader:
```
    
export PYTHONPATH="$PWD/src"
$env:PYTHONPATH="$PWD/src"
python -m solar_controller.main


## Architecture Overview

The SolarEdgeController project is structured around a **decoupled, interface-driven architecture**.
All hardware-specific logic (Modbus, ESPHome, SunSpec) is isolated behind standardized interfaces,
allowing control logic and Home Assistant integration to remain vendor-agnostic.

Core architectural goals:

- Clear separation of concerns
- Hardware-agnostic control logic
- Explicit, standardized interfaces
- Metadata-driven device definitions
- Asynchronous, non-blocking I/O



## Project Structure
The project is organized into several layers, each with a specific responsibility:
```text
src/solar_controller/
├── base/               # Abstract base interfaces
│   ├── inverter.py
│   └── sensor.py
├── controller/         # Control logic (regulation algorithms)
│   └── solar_regulator.py
├── factories/          # Device factories
│   ├── inverter_factory.py
│   └── sensor_factory.py
├── inverter/           # Inverter implementations
│   ├── solaredge_inverter.py
│   └── solaredge_inverter_registers.py
├── sensors/            # Sensor implementations
│   └── esphome_reader.py
├── config.py
├── logger.py
└── main.py
```



## Architectural Layers

### 1. Device Drivers

Device drivers handle **protocol-specific communication**:

- SolarEdge inverter via Modbus (SunSpec)
- Grid and auxiliary sensors via ESPHome API

Responsibilities:

- Connection handling
- Decoding raw values
- Applying scaling factors
- Caching state locally

Device drivers **must not contain control logic**.

---

### 2. Standardized Interfaces

All devices expose **semantic, vendor-independent interfaces**.
These interfaces are the only way higher layers interact with hardware.

Consumers:

- Control / regulation logic
- Home Assistant integration
- Tests and simulations

---

## Control Data Interface

### `get_control_data()`

All devices that participate in the control loop must implement:

```python
get_control_data() -> dict[str, Any]
```

### Purpose

- Decouple internal register or entity names from control logic
- Provide semantic, stable field names
- Allow different hardware implementations to be swapped
- Prevent protocol or register leakage into regulation code

---

### Inverter: `get_control_data()`

Inverter implementations return:

```python
{
    "solar_production": float | None,   # Current AC production power (W)
    "power_limit": int | None,          # Active power limit (%)
    "last_updated": float | None        # Unix timestamp of last successful update
}
```

Characteristics:

- Values are already scaled
- Scale-factor registers are excluded
- Keys are stable and vendor-agnostic
- Safe for direct use by control logic

---

### ESPHome Sensor: `get_control_data()`

ESPHome sensors expose raw entities and require decoupling to a standardized control interface.

The method now returns **vendor-agnostic, semantic keys** in the format:

```python
{
    "grid_import_power": [value: float | "<no value>", last_updated: float | None],
    "grid_export_power": [value: float | "<no value>", last_updated: float | None]
}
```
The returned value whould be in Watts (W). If a sensor has never reported a value, it returns `"<no value>"`.

### Purpose

- Decouple ESPHome object IDs from the control loop.
- Provide a consistent interface for regulation logic.
- Preserve both the latest value and timestamp per sensor.
- Handle missing or never-reported values gracefully.

### Notes

- Values are floats when reported, `"<no value>"` if the sensor has never reported.
- `last_updated` is a float timestamp of the last measurement, or `None` if no value exists.
- No I/O is performed; the method returns immediately from cached state.
- Fully compatible with the control interface expected by other hardware drivers.

Example output:

```python
{
    "grid_import_power": [1.6, 1768140230.9362214],
    "grid_export_power": [227.7, 1768140230.9363801]
}
```

This approach ensures that control logic **only depends on semantic keys** and not on any ESPHome-specific naming.

---

## Home Assistant Sensor Interface

### `get_ha_sensors()`

All devices that expose telemetry to Home Assistant must implement:

```python
get_ha_sensors(group: Optional[Enum] = None) -> dict[str, dict]
```

### Purpose

- Produce Home Assistant–ready sensor definitions
- Centralize Home Assistant metadata
- Avoid duplicated HA configuration logic

### Behavior Guarantees

- Returned values are fully scaled
- Scale-only registers are never exposed
- Each sensor definition includes:

```python
{
    "state",
    "unit",
    "device_class",
    "state_class",
    "entity_category",
    "icon",
    "friendly_name",
    "description",
    "unique_id",
    "available"
}
```

Guarantees:

- Zero post-processing in Home Assistant
- Stable entity IDs
- Correct device and entity registry behavior

---

## Inverter Update Interface

Inverter implementations must expose explicit asynchronous update methods:

```python
async def update_poll_registers(self) -> None
async def update_control_registers(self) -> None
async def update_status_registers(self) -> None
```

### Rationale

- Fine-grained control of Modbus traffic
- Deterministic scheduling
- Alignment with SunSpec register groups
- Reduced unnecessary I/O

Each method:

- Executes blocking I/O in a thread executor
- Applies scaling automatically
- Updates cached attributes
- Refreshes the `last_updated` timestamp

---

## Device Factories

Device instantiation is centralized in simple factories:

- `inverter_factory.create_inverter(config)`
- `sensor_factory.create_sensor(config)`

Benefits:

- Centralized configuration handling
- Easy replacement of implementations
- No direct imports of concrete classes in control logic

---

## Interface Summary

| Interface | Inverter | ESPHome Sensor |
|---------|----------|----------------|
| `get_control_data()` | Implemented | Implemented |
| `get_ha_sensors()` | Implemented | Implemented |
| Async update methods | Required | Not applicable |
| Vendor-agnostic semantics | Yes | Partial |

---

## Architectural Rule

> Control logic must never depend on registers, entity IDs, or communication protocols.

All interactions are mediated exclusively through:

- `get_control_data()` for regulation decisions
- `get_ha_sensors()` for observability

This ensures maintainability, extensibility, and a clean separation of concerns.
