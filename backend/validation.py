"""Validate device telemetry before database writes or online status changes."""
import math
import re

def validate_telemetry(data):
    if not isinstance(data, dict):
        raise ValueError("telemetry must be an object")
    device=data.get("device")
    if not isinstance(device,str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}",device):
        raise ValueError("invalid device")
    required={"soil_raw":(0,1023),"soil_moisture":(0,100),"movement_cm":(0,400)}
    optional={"temperature":(-40,80),"humidity":(0,100),"distance":(2,400),
              "baseline_distance":(2,400),"wifi_rssi":(-127,0),"uptime_ms":(0,4294967295)}
    for field,(low,high) in {**required,**optional}.items():
        if field not in data:
            if field in required:raise ValueError("missing "+field)
            continue
        value=data[field]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not low<=value<=high or not math.isfinite(value):
            raise ValueError("invalid "+field)
    for field in ("rain","vibration","movement"):
        if type(data.get(field)) is not bool:raise ValueError("invalid "+field)
    if data.get("risk_level") not in ("NORMAL","WARNING","DANGER"):
        raise ValueError("invalid risk_level")
    health=data.get("sensor_health")
    if not isinstance(health,dict) or set(health)!={"soil","rain","vibration","dht11","hc_sr04"}:
        raise ValueError("invalid sensor_health")
    if any(v not in ("OK","ERROR","UNKNOWN") for v in health.values()):
        raise ValueError("invalid sensor health state")
    if health["dht11"]=="OK" and not all(k in data for k in ("temperature","humidity")):
        raise ValueError("DHT11 OK requires temperature and humidity")
    if health["hc_sr04"]=="OK" and "distance" not in data:
        raise ValueError("HC-SR04 OK requires distance")
    # Store only supported fields; never accept device-controlled server timestamps/IDs.
    keys=set(required)|set(optional)|{"device","rain","vibration","movement","risk_level","sensor_health"}
    return {k:v for k,v in data.items() if k in keys}
