import unittest,sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from validation import validate_telemetry
class ValidationTests(unittest.TestCase):
 def sample(self):return dict(device='station01',soil_raw=500,soil_moisture=50,movement_cm=0,rain=False,vibration=False,movement=False,temperature=28,humidity=65,distance=20,risk_level='NORMAL',sensor_health={k:'OK' for k in ['soil','rain','vibration','dht11','hc_sr04']})
 def test_valid(self):self.assertEqual(validate_telemetry(self.sample())['soil_raw'],500)
 def test_invalid(self):
  for field,values in {'soil_raw':[-1,1024,True], 'soil_moisture':[-1,101,math.nan], 'rain':[1,'false'], 'movement_cm':[math.inf,-1], 'risk_level':['Warning','<img>','INVALID'], 'sensor_health':[{},None]}.items():
   for value in values:
    with self.subTest(field=field,value=value):
     d=self.sample();d[field]=value
     with self.assertRaises(ValueError):validate_telemetry(d)
 def test_missing_fields(self):
  for key in self.sample():
   d=self.sample();del d[key]
   with self.subTest(key=key),self.assertRaises(ValueError):validate_telemetry(d)
 def test_sensor_error_can_omit_reading(self):
  d=self.sample();d['sensor_health']['dht11']='ERROR';del d['temperature'];del d['humidity'];self.assertIn('device',validate_telemetry(d))
 def test_server_fields_not_trusted(self):
  d=self.sample();d['_id']='x';d['timestamp']='x';self.assertNotIn('_id',validate_telemetry(d));self.assertNotIn('timestamp',validate_telemetry(d))
