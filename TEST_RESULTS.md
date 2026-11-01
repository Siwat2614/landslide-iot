# Test results — 2026-11-01

Executed on macOS ARM64 with Docker Desktop, MongoDB 7 and Mosquitto 2.

- PASS: dashboard HTTP
- PASS: MongoDB + MQTT health
- PASS: no device OFFLINE
- PASS: MQTT to DB to latest
- PASS: device ONLINE
- PASS: risk transition events
- PASS: command API to MQTT
- PASS: invalid command 400
- PASS: malformed JSON does not crash API
- PASS: device timeout OFFLINE
- PASS: history limit
- PASS: invalid sensor object rejected

- Python validation unit tests: PASS (including invalid types, ranges and non-finite numbers).
- MQTT broker restart and automatic reconnection: PASS.
- Native C++ protocol/risk regression tests: PASS.

Hardware sensor readings, full Arduino firmware compilation and physical LED output have not been verified. No deployment configured.
