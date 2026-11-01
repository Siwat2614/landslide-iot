import json, os
from validation import validate_telemetry
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from pymongo.errors import PyMongoError

MONGO_URL=os.getenv("MONGO_URL","mongodb://mongodb:27017")
MQTT_HOST=os.getenv("MQTT_HOST","mosquitto"); MQTT_PORT=int(os.getenv("MQTT_PORT","1883"))
TELEMETRY_TIMEOUT_SECONDS=int(os.getenv("TELEMETRY_TIMEOUT_SECONDS","8"))
TOPIC_SENSOR="landslide/sensor"; TOPIC_STATUS="landslide/status"; TOPIC_COMMAND="landslide/command"
mongo=MongoClient(MONGO_URL,serverSelectionTimeoutMS=3000,tz_aware=True); db=mongo["landslide"]
sensors=db["sensor_data"]; events_col=db["events"]; systems=db["system_status"]
client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2); last_risk=None

def now(): return datetime.now(timezone.utc)
def ser(d):
    if not d:return {}
    d=dict(d)
    d["_id"]=str(d["_id"]);return d

def on_connect(c,u,f,rc,p):
    print("MQTT connected",rc);c.subscribe(TOPIC_SENSOR);c.subscribe(TOPIC_STATUS)

def on_message(c,u,msg):
    global last_risk
    try:
        text=msg.payload.decode("utf-8",errors="replace")
        if msg.topic==TOPIC_STATUS:
            if text not in ("ONLINE","OFFLINE"):return
            systems.update_one({"_id":"esp8266"},{"$set":{"status":text,"status_timestamp":now()}},upsert=True);return
        if msg.topic!=TOPIC_SENSOR:return
        data=validate_telemetry(json.loads(text));data["timestamp"]=now();sensors.insert_one(data.copy())
        systems.update_one({"_id":"esp8266"},{"$set":{"last_seen":data["timestamp"],"device":data.get("device","unknown")}},upsert=True)
        risk=data.get("risk_level")
        if risk and risk!=last_risk:
            events_col.insert_one({"type":"RISK_CHANGE","risk_level":risk,"timestamp":now()});last_risk=risk
    except Exception as e: print("MQTT message error",e)
client.on_connect=on_connect;client.on_message=on_message

@asynccontextmanager
async def lifespan(app):
    sensors.create_index([("timestamp",-1)]);events_col.create_index([("timestamp",-1)])
    client.connect_async(MQTT_HOST,MQTT_PORT,60);client.loop_start();yield
    client.loop_stop();client.disconnect();mongo.close()

app=FastAPI(title="IoT Landslide Risk Monitoring API",version="1.0.0",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])

@app.get("/")
def root():return {"system":"IoT Landslide Risk Monitoring System","status":"running"}
@app.get("/health")
def health():
    ok=False
    try:mongo.admin.command("ping");ok=True
    except PyMongoError:pass
    return {"api":"online","mongodb":"connected" if ok else "disconnected","mqtt":"connected" if client.is_connected() else "disconnected"}
@app.get("/api/latest")
def latest():return ser(sensors.find_one(sort=[("timestamp",-1)]))
@app.get("/api/history")
def history(limit:int=Query(50,ge=1,le=500)):return [ser(x) for x in sensors.find().sort("timestamp",-1).limit(limit)]
@app.get("/api/events")
def events(limit:int=Query(30,ge=1,le=200)):return [ser(x) for x in events_col.find().sort("timestamp",-1).limit(limit)]
@app.get("/api/device-status")
def device_status():
    status=systems.find_one({"_id":"esp8266"}) or {}
    latest_reading=sensors.find_one(sort=[("timestamp",-1)])
    last_seen=latest_reading.get("timestamp") if latest_reading else status.get("last_seen")
    if last_seen and last_seen.tzinfo is None:last_seen=last_seen.replace(tzinfo=timezone.utc)
    age_seconds=None if not last_seen else max(0,(now()-last_seen).total_seconds())
    online=age_seconds is not None and age_seconds <= TELEMETRY_TIMEOUT_SECONDS and status.get("status") != "OFFLINE"
    sensor_health=(latest_reading or {}).get("sensor_health",{})
    sensors_status={name:sensor_health.get(name,"UNKNOWN") for name in ("soil","rain","vibration","dht11","hc_sr04")}
    return {"device":status.get("device","landslide-01"),"status":"ONLINE" if online else "OFFLINE",
            "online":online,"last_seen":last_seen,"age_seconds":age_seconds,
            "telemetry_timeout_seconds":TELEMETRY_TIMEOUT_SECONDS,"sensors":sensors_status}
@app.post("/api/command/{command}")
def command(command:str):
    allowed={"LED_ON","LED_OFF","SET_BASELINE"}
    if command not in allowed:raise HTTPException(400,detail=f"Allowed: {sorted(allowed)}")
    if not client.is_connected():raise HTTPException(503,detail="MQTT disconnected")
    r=client.publish(TOPIC_COMMAND,command)
    if r.rc!=mqtt.MQTT_ERR_SUCCESS:raise HTTPException(503,detail="MQTT publish failed")
    events_col.insert_one({"type":"COMMAND","command":command,"timestamp":now()});return {"success":True,"command":command}
