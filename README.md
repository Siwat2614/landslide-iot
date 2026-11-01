# Landslide IoT — ESP8266 educational prototype

ESP8266 reads soil moisture, rain, vibration, DHT11 and HC-SR04, publishes MQTT, then FastAPI/MongoDB and a dashboard display the readings. **Not a real landslide warning device.** Risk thresholds are demonstration values requiring calibration; passing software tests does not establish warning accuracy.

## Local startup

```sh
cp .env.example .env
docker compose -p landslide-iot up -d --build
```

Dashboard http://127.0.0.1:18082 · API docs http://127.0.0.1:18002/docs · health through dashboard `/health`. MQTT host port 28884. Stop using `docker compose -p landslide-iot down` (keeps DB).

## Hardware

NodeMCU 1.0 ESP-12E; libraries PubSubClient, ArduinoJson 6.x, DHT sensor library, Adafruit Unified Sensor. Sketch: `firmware/landslide_esp8266/landslide_esp8266.ino`.

| Signal | NodeMCU |
|---|---|
| Soil AO | A0 |
| Rain DO | D5 |
| Vibration DO | D6 |
| DHT11 | D7 |
| HC-SR04 TRIG | D1 |
| HC-SR04 ECHO | D2 through voltage divider |

**Do not connect 5V ECHO directly to ESP8266.** Original wiring uses 1kΩ from ECHO to D2 junction and 2kΩ from junction to GND. Verify hardware ratings. Keep electronics away from water.

Set WIFI_SSID, WIFI_PASSWORD and MQTT_SERVER to your actual local values without committing credentials. Firmware broker host port is 28884. To connect a physical board, set MQTT_BIND in .env to the Mac LAN IP (or 0.0.0.0 in a trusted isolated lab). ESP and Mac must share the network. Calibrate SOIL_DRY_RAW / SOIL_WET_RAW, active levels and marker baseline on the real model.

## Corrected behavior

- Score >=4 → DANGER, >=2 → WARNING, otherwise NORMAL; labels are uppercase and shared risk code is tested across 48 boundary combinations.
- Reject missing fields, wrong types, non-finite/out-of-range measurements and invalid risk/health labels before DB writes or ONLINE updates. Missing DHT/ultrasonic readings are allowed only with non-OK sensor health.
- Device status requires fresh valid telemetry; timeout is 8 seconds. Dashboard displays UNKNOWN for offline devices and never describes unknown risk as normal.
- MQTT reconnects asynchronously. Commands return 503 if disconnected. Command success only means the broker accepted publication; there is no hardware acknowledgement protocol.
- MongoDB timestamps serialize with timezone information. Event values use DOM text instead of interpreting HTML.

MQTT topics: landslide/sensor, landslide/status, landslide/command. Risk is calculated by firmware; server validates its enum but does not independently certify the risk assessment. Single-device design.

## API

GET /health, /api/latest, /api/history, /api/events, /api/device-status.
POST /api/command/LED_ON, /LED_OFF, /SET_BASELINE (full prefix for each).

## Tests

```sh
docker run --rm --network none -v "$PWD:/work:ro" -w /work landslide-iot-backend python -m unittest discover -s tests -v
c++ tests/test_risk.cpp -o /tmp/test-risk && /tmp/test-risk
MQTT_CONTAINER=landslide-iot-mosquitto-1 python3 tests/integration.py
```

Integration tests require a separate fresh test database and insert simulated records. BASE_URL / MQTT_CONTAINER can select test instances. See TEST_RESULTS.md. Full Arduino compilation, calibration and physical hardware are not verified.

No deployment is configured. MQTT/API are unauthenticated lab services; keep them isolated and add authentication/TLS before external use. Never commit Wi-Fi credentials or .env.
