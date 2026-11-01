import os,json,time,subprocess,urllib.request,urllib.error
from pathlib import Path
base=os.getenv('BASE_URL','http://127.0.0.1:18082');results=[]
def req(path,method='GET'):
 try:
  with urllib.request.urlopen(urllib.request.Request(base+path,method=method),timeout=10) as r:return r.status,json.loads(r.read())
 except urllib.error.HTTPError as e:return e.code,e.read().decode()
def check(n,ok,d=''):results.append({'test':n,'pass':bool(ok),'detail':d});print(n,ok,d,flush=True)
def pub(topic,payload):subprocess.run(['docker','exec',os.getenv('MQTT_CONTAINER','landslide-iot-mosquitto-1'),'mosquitto_pub','-t',topic,'-m',payload,'-q','1'],capture_output=True,check=True)
check('dashboard HTTP',urllib.request.urlopen(base).status==200)
c,d=req('/health');check('MongoDB + MQTT health',c==200 and d['mongodb']=='connected' and d['mqtt']=='connected',d)
check('no device OFFLINE',req('/api/device-status')[1]['status']=='OFFLINE')
health={k:'OK' for k in ['soil','rain','vibration','dht11','hc_sr04']}
data={'device':'qa-landslide','soil_moisture':32,'soil_raw':640,'rain':False,'vibration':False,'temperature':28,'humidity':65,'distance':20,'movement_cm':0,'movement':False,'risk_level':'NORMAL','sensor_health':health}
pub('landslide/status','ONLINE');pub('landslide/sensor',json.dumps(data));time.sleep(1)
c,d=req('/api/latest');check('MQTT to DB to latest',c==200 and d.get('soil_moisture')==32,d)
check('device ONLINE',req('/api/device-status')[1]['status']=='ONLINE')
for risk in ['WARNING','DANGER']:
 data['risk_level']=risk;pub('landslide/sensor',json.dumps(data));time.sleep(.3)
c,d=req('/api/events');check('risk transition events',c==200 and {'NORMAL','WARNING','DANGER'}<=set(x.get('risk_level') for x in d),len(d))
sub=subprocess.Popen(['docker','exec',os.getenv('MQTT_CONTAINER','landslide-iot-mosquitto-1'),'mosquitto_sub','-t','landslide/command','-C','1','-W','5'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);time.sleep(.3)
c,d=req('/api/command/LED_ON','POST');stdout,stderr=sub.communicate(timeout=8);check('command API to MQTT',c==200 and stdout.strip()=='LED_ON',{'api':d,'mqtt':stdout.strip()})
check('invalid command 400',req('/api/command/NOT_ALLOWED','POST')[0]==400)
pub('landslide/sensor','{bad-json');time.sleep(.3);check('malformed JSON does not crash API',req('/health')[0]==200)
print('Waiting 9 seconds for OFFLINE',flush=True);time.sleep(9);check('device timeout OFFLINE',req('/api/device-status')[1]['status']=='OFFLINE')
c,d=req('/api/history?limit=2');check('history limit',c==200 and len(d)==2)
pub('landslide/sensor',json.dumps({'invalid':'not-a-sensor'}));time.sleep(.5);c,d=req('/api/latest');check('invalid sensor object rejected','invalid'not in d,{'stored':d})
Path(__file__).with_name('integration-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
