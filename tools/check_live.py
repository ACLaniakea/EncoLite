"""Read-only connection check, no setting commands."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from encolite.bluetooth_windows import discover
from encolite.live_session import LiveSession
s=LiveSession()
try:
    devices=discover()
    if not devices: raise RuntimeError('No paired OPPO headset')
    s.connect(next((d for d in devices if d.connected),devices[0]))
    print(json.dumps(dict(connected=s.connected,name=s.device_name,product=s.product_id,firmware=s.firmware,noise=s.noise,preset=s.preset,features=s.features,game_sound=s.game_sound,spatial=s.spatial_mode,bass=s.bass_state,custom=[e.__dict__ for e in s.custom_entries],multi=s.multi_devices,wear=s.wear_state,codec=s.codec,events=sorted(s.registered_events),available={k:s.supported(k) for k in ['wear','dual','voice','long','hearing','game','game_sound','bass','spatial','spatial_audio','custom','multi','multi_write','find']},trace=list(s.trace)),ensure_ascii=True,indent=2))
finally:
    s.close()
