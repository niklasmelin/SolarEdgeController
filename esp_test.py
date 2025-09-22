import asyncio, math
from aioesphomeapi import (
    APIClient, APIConnectionError,
    SensorInfo, BinarySensorInfo, TextSensorInfo,
)

HOST = "192.168.30.182"
PORT = 6053
ENCRYPTION_KEY = ""
WINDOW_SECONDS = 6  # increase to 8–10 if needed

async def main():
    client = APIClient(HOST, PORT, password="", noise_psk=ENCRYPTION_KEY)
    try:
        await client.connect(login=True)

        # discover entities
        entities, _ = await client.list_entities_services()
        meta = {}  # key -> (object_id, name, unit, kind)
        for ent in entities:
            if isinstance(ent, SensorInfo):
                meta[ent.key] = (ent.object_id, ent.name, ent.unit_of_measurement or "", "sensor")
            elif isinstance(ent, BinarySensorInfo):
                meta[ent.key] = (ent.object_id, ent.name, "", "binary_sensor")
            elif isinstance(ent, TextSensorInfo):
                meta[ent.key] = (ent.object_id, ent.name, "", "text_sensor")

        if not meta:
            print("No sensor/binary_sensor/text_sensor entities found.")
            return

        # collect first value seen per entity
        states = {}
        def on_state(msg):
            k = getattr(msg, "key", None)
            if k not in meta or k in states:
                return
            kind = meta[k][3]
            if kind == "sensor" and hasattr(msg, "state"):
                v = msg.state
                if v is None or (isinstance(v, float) and math.isnan(v)):
                    return
                states[k] = v
            elif kind == "binary_sensor" and hasattr(msg, "state"):
                states[k] = bool(msg.state)
            elif kind == "text_sensor" and hasattr(msg, "state") and msg.state is not None:
                states[k] = msg.state

        # subscribe (do NOT await; not a coroutine in many versions)
        client.subscribe_states(on_state)

        # allow time for the device to push current states
        # await asyncio.sleep(WINDOW_SECONDS)

        # print snapshot
        print("Entities (sensor/binary_sensor/text_sensor):")
        for key, (obj_id, name, unit, kind) in meta.items():
            v = states.get(key)
            unit = unit or ""
            if v is None:
                print(f"  {obj_id:<32} {name:<32} <no value>")
            else:
                if kind == "binary_sensor":
                    v = "ON" if v else "OFF"
                print(f"  {obj_id:<36} {name:<36} {round(v,1):>8} {unit}")

    except APIConnectionError as e:
        print("Failed to connect:", e)
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
