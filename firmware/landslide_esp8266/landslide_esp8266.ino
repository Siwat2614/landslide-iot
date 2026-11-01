#include "risk_rules.h"
#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHT.h>

const char* WIFI_SSID="YOUR_WIFI_SSID";
const char* WIFI_PASSWORD="YOUR_WIFI_PASSWORD";
const char* MQTT_SERVER="192.168.1.100";
const uint16_t MQTT_PORT=28884;
const char* TOPIC_SENSOR="landslide/sensor";
const char* TOPIC_STATUS="landslide/status";
const char* TOPIC_COMMAND="landslide/command";

#define SOIL_PIN A0
#define RAIN_PIN D5
#define VIBRATION_PIN D6
#define DHT_PIN D7
#define DHT_TYPE DHT11
#define TRIG_PIN D1
#define ECHO_PIN D2
#define STATUS_LED LED_BUILTIN

const bool RAIN_ACTIVE_LOW=true;
const bool VIBRATION_ACTIVE_LOW=true;
int SOIL_DRY_RAW=800;     // CALIBRATE
int SOIL_WET_RAW=300;     // CALIBRATE
int SOIL_WARNING_PERCENT=60; // demo/model only
int SOIL_DANGER_PERCENT=80;  // demo/model only
float MOVEMENT_THRESHOLD_CM=3.0; // demo/model only
const unsigned long SEND_INTERVAL_MS=2000;

DHT dht(DHT_PIN,DHT_TYPE);
WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);
float baselineDistanceCm=-1;
unsigned long lastSendMs=0;
bool vibrationLatched=false;

bool activeDigital(uint8_t pin,bool activeLow){int v=digitalRead(pin);return activeLow?v==LOW:v==HIGH;}
int soilPercent(int raw){long p=map(raw,SOIL_DRY_RAW,SOIL_WET_RAW,0,100);return constrain((int)p,0,100);}

float readDistanceOnce(){
  digitalWrite(TRIG_PIN,LOW); delayMicroseconds(2);
  digitalWrite(TRIG_PIN,HIGH); delayMicroseconds(10); digitalWrite(TRIG_PIN,LOW);
  unsigned long duration=pulseIn(ECHO_PIN,HIGH,30000UL);
  if(duration==0)return -1;
  float cm=duration*0.0343f/2.0f;
  return (cm>=2 && cm<=400)?cm:-1;
}
float readDistance(){float total=0;int n=0;for(int i=0;i<3;i++){float d=readDistanceOnce();if(d>0){total+=d;n++;}delay(20);}return n?total/n:-1;}

String riskLevel(int soil,bool rain,bool vibration,bool movement){
  return classifyRisk(soil,rain,vibration,movement,SOIL_WARNING_PERCENT,SOIL_DANGER_PERCENT);
}

void connectWiFi(){
  if(WiFi.status()==WL_CONNECTED)return;
  WiFi.mode(WIFI_STA); WiFi.begin(WIFI_SSID,WIFI_PASSWORD);
  Serial.print("Connecting Wi-Fi"); unsigned long t=millis();
  while(WiFi.status()!=WL_CONNECTED && millis()-t<20000){delay(500);Serial.print(".");}
  if(WiFi.status()==WL_CONNECTED){Serial.print("\nIP: ");Serial.println(WiFi.localIP());}
  else Serial.println("\nWi-Fi timeout; retrying later");
}

void callback(char*,byte* payload,unsigned int length){
  String msg; for(unsigned int i=0;i<length;i++)msg+=(char)payload[i]; msg.trim();
  Serial.print("Command: ");Serial.println(msg);
  if(msg=="LED_ON")digitalWrite(STATUS_LED,LOW);
  else if(msg=="LED_OFF")digitalWrite(STATUS_LED,HIGH);
  else if(msg=="SET_BASELINE"){float d=readDistance();if(d>0){baselineDistanceCm=d;Serial.printf("Baseline %.1f cm\n",d);}}
}

void connectMQTT(){
  if(mqtt.connected()||WiFi.status()!=WL_CONNECTED)return;
  String id="ESP8266-Landslide-"+String(ESP.getChipId(),HEX);
  if(mqtt.connect(id.c_str(),TOPIC_STATUS,0,true,"OFFLINE")){
    mqtt.subscribe(TOPIC_COMMAND); mqtt.publish(TOPIC_STATUS,"ONLINE",true); Serial.println("MQTT connected");
  } else {Serial.print("MQTT failed rc=");Serial.println(mqtt.state());}
}

void setup(){
  Serial.begin(115200);
  pinMode(RAIN_PIN,INPUT);pinMode(VIBRATION_PIN,INPUT);pinMode(TRIG_PIN,OUTPUT);pinMode(ECHO_PIN,INPUT);
  pinMode(STATUS_LED,OUTPUT);digitalWrite(STATUS_LED,HIGH);dht.begin();
  connectWiFi();mqtt.setServer(MQTT_SERVER,MQTT_PORT);mqtt.setCallback(callback);mqtt.setBufferSize(768);connectMQTT();
  delay(1000);baselineDistanceCm=readDistance();Serial.printf("Initial baseline %.1f cm\n",baselineDistanceCm);
}

void loop(){
  if(activeDigital(VIBRATION_PIN,VIBRATION_ACTIVE_LOW))vibrationLatched=true;
  if(WiFi.status()!=WL_CONNECTED)connectWiFi();
  if(!mqtt.connected()){static unsigned long lastTry=0;if(millis()-lastTry>3000){lastTry=millis();connectMQTT();}}
  mqtt.loop();
  if(millis()-lastSendMs<SEND_INTERVAL_MS){delay(5);return;} lastSendMs=millis();

  int raw=analogRead(SOIL_PIN),soil=soilPercent(raw);
  bool rain=activeDigital(RAIN_PIN,RAIN_ACTIVE_LOW),vibration=vibrationLatched;vibrationLatched=false;
  float temp=dht.readTemperature(),hum=dht.readHumidity();
  if(isnan(temp)||isnan(hum)){delay(1100);temp=dht.readTemperature();hum=dht.readHumidity();}
  float distance=readDistance();
  if(baselineDistanceCm<=0 && distance>0)baselineDistanceCm=distance;
  float movementCm=(distance>0&&baselineDistanceCm>0)?fabs(distance-baselineDistanceCm):0;
  bool movement=movementCm>=MOVEMENT_THRESHOLD_CM;
  String risk=riskLevel(soil,rain,vibration,movement);

  StaticJsonDocument<640> doc;
  doc["device"]="landslide-01";doc["soil_raw"]=raw;doc["soil_moisture"]=soil;doc["rain"]=rain;doc["vibration"]=vibration;
  if(!isnan(temp))doc["temperature"]=temp;if(!isnan(hum))doc["humidity"]=hum;if(distance>0)doc["distance"]=distance;
  if(baselineDistanceCm>0)doc["baseline_distance"]=baselineDistanceCm;doc["movement_cm"]=movementCm;doc["movement"]=movement;
  JsonObject health=doc.createNestedObject("sensor_health");
  health["soil"]="OK";health["rain"]="OK";health["vibration"]="OK";
  health["dht11"]=(isnan(temp)||isnan(hum))?"ERROR":"OK";
  health["hc_sr04"]=distance>0?"OK":"ERROR";
  doc["risk_level"]=risk;doc["wifi_rssi"]=WiFi.RSSI();doc["uptime_ms"]=millis();
  char out[640];size_t n=serializeJson(doc,out,sizeof(out));if(mqtt.connected())mqtt.publish(TOPIC_SENSOR,out,n);Serial.println(out);
}
