"""Exercise reversible X3 settings, restore original values in finally.
Never rings find-device or unpairs/disconnects another Bluetooth host.
"""
from pathlib import Path
import sys,json,traceback,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from encolite.bluetooth_windows import discover
from encolite.live_session import LiveSession
from encolite.oppo_features import CustomEQ
s=LiveSession(); report={'model':'','firmware':'','checks':[],'restoration':[]}; created=None; initial=None

def check(name,fn):
    try:
        fn(); report['checks'].append({'name':name,'result':'PASS'}); print('PASS',name,flush=True)
    except Exception as error:
        report['checks'].append({'name':name,'result':'FAIL','error':str(error)}); print('FAIL',name,str(error),flush=True)

try:
    device=next(d for d in discover() if 'X3' in d.name)
    s.connect(device)
    report['model']=s.device_name; report['firmware']=s.firmware
    initial=dict(noise=s.noise,preset=s.preset,spatial=s.spatial_mode,game_sound=s.game_sound,features={k:s.feature_value(k) for k in ('wear','dual','hearing','game') if s.feature_available(k)})
    report['initial']=initial
    for mode in s.noise_modes:
        check('noise:'+mode,lambda mode=mode:s.set_noise(mode))
    for p in s.profile['presets']:
        check('equalizer:'+str(p['id']),lambda p=p:s.set_preset(p['id']))
    s.set_preset(initial['preset'])
    for mode in s.profile.get('spatial_types',[]):
        if s.supported('spatial_audio'): check('spatial:'+str(mode),lambda mode=mode:s.set_spatial(mode))
    for key in ('wear','hearing','game'):
        if key in initial['features']:
            check('feature:'+key,lambda key=key:(s.set_feature(key,not initial['features'][key]),s.set_feature(key,initial['features'][key])))
    if 'dual' in initial['features']:
        check('dual:idempotent',lambda:s.set_feature('dual',initial['features']['dual']))
    for value in s.profile.get('game_types',[]):
        check('game_sound:'+str(value),lambda value=value:s.set_game_sound(value))
    s.set_game_sound(initial['game_sound'])
    if s.supported('custom'):
        def custom():
            global created
            name='EncoCheck'+str(int(time.time())%100000)
            entry=CustomEQ(0,name,tuple(s.profile['frequencies']),tuple(0 for _ in s.profile['frequencies']))
            created=s.write_custom(1,entry)
            edited=CustomEQ(created.id,name,created.frequencies,tuple(1 for _ in created.gains),created.minimum,created.maximum)
            s.write_custom(2,edited)
            s.set_preset(initial['preset'])
            s.write_custom(3,edited); created=None
        check('custom:create-update-select-delete',custom)
    check('refresh:wear-multi-battery-codec',s.refresh)
    report['readback']={'battery':{k:v.percent if v else None for k,v in s.battery.items()},'custom_count':len(s.custom_entries),'connected_hosts':sum(d['state']==2 for d in s.multi_devices),'codec':s.codec,'subscribed':sorted(s.registered_events)}
finally:
    if initial and s.connected:
        restore=[('game_sound',lambda:s.set_game_sound(initial['game_sound']))]
        restore.extend((k,lambda k=k,v=v:s.set_feature(k,v)) for k,v in initial['features'].items() if k!='dual')
        restore.extend([('spatial',lambda:s.set_spatial(initial['spatial'])),('preset',lambda:s.set_preset(initial['preset'])),('noise',lambda:s.set_noise(initial['noise']))])
        if created: restore.append(('delete-created-only',lambda:s.write_custom(3,created)))
        for name,fn in restore:
            try: fn(); report['restoration'].append({'name':name,'result':'PASS'})
            except Exception as error: report['restoration'].append({'name':name,'result':'FAIL','error':str(error)})
    s.close()
    out=Path(__file__).resolve().parents[1]/'verification/x3-hardware.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2),flush=True)
