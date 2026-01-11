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
