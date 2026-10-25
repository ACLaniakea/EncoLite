"""Read-only Bluetooth handshake/readback using the packaged runtime."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from encolite.bluetooth_windows import discover
from encolite.live_session import LiveSession
report={'result':'FAIL','errors':[]}
session=LiveSession()
try:
    devices=discover()
    device=next((d for d in devices if 'X3' in d.name),None)
    if device is None:
        report['result']='SKIP';report['reason']='No paired Enco X3 found'
    else:
        session.connect(device)
        report.update(result='PASS',model=session.device_name,firmware=session.firmware,
            product_id=session.product_id,noise=session.noise,preset=session.preset,
            battery={k:v.percent if v else None for k,v in session.battery.items()},
            codec=session.codec,subscribed=sorted(session.registered_events))
except Exception as error:report['errors'].append(repr(error))
finally:
    session.close()
    (ROOT/'verification/native-bluetooth.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(report,ensure_ascii=True),flush=True)
    if report['result']=='FAIL':raise SystemExit(1)
