"""Import the upstream OPPO/OnePlus whitelist, preserving real protocol indices."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT.parent/'OppoPodsManager-upstream/Assets/Oplus/Data'
NAMES=json.loads((SOURCE/'EqModeNames.json').read_text('utf-8-sig'))['mapping']
MODES={1:'off',2:'transparency',3:'light',4:'deep',5:'nc',6:'vocal',7:'smart',8:'moderate',10:'adaptive'}
KEYS={'wear':'wearDetection','dual':'multiDevicesConnect','voice':'vocalEnhance','long':'longPowerMode','bass':'bassEngineSupport','find':'findDevice','hearing':'hearingEnhancement','custom':'customEqualizer'}

def enabled(value):
    return isinstance(value,(bool,int)) and value>0

def profile(entry):
    f=entry.get('function',{})
    result=dict(id=entry['id'].upper(),name=entry['name'],noise={},presets=[],**{k:enabled(f.get(v)) for k,v in KEYS.items()})
    result.update(brand='OnePlus' if entry.get('brand','').casefold()=='oneplus' else 'OPPO',
        aliases=list(dict.fromkeys(child['name'] for child in entry.get('children',[]) if child.get('name') and child['name']!=entry['name'])),
        product_aliases=list(dict.fromkeys(child['id'].upper() for child in entry.get('children',[]) if child.get('id'))),
        service_uuid=entry.get('uuid','0000079A-D102-11E1-9B23-00025B00A5A5').lower(),
        support_spp=entry.get('supportSpp',True),form_factor=entry.get('type',''))
    result['hearing'] |= bool(f.get('hearingEnhancementNew'))
    result['game']=any(x.get('gameMode')==1 for x in f['gameModeList']) if f.get('gameModeList') else enabled(f.get('gameMode'))
    result['game_types']=[x['type'] for x in f.get('gameSoundList',[]) if isinstance(x.get('type'),int)]
    result['game'] |= bool(result['game_types'])
    result['multi']=bool(f.get('multiConnectFunctions')) or result['dual']
    result['spatial_types']=f.get('spatialTypes',[])
    result['mutex']=f.get('gameSoundMutexes',[])
    result['eq_mutex']=bool({1,3}&set(result['mutex']))
    result['frequencies']=f.get('customEqFrequency') or [62,250,1000,4000,8000,16000]
    result['custom_max']=f.get('customEqMax',0)
    result['battery_layout']=f.get('batteryLayout','Auto')
    for group in f.get('noiseReductionMode',[]):
        children=group.get('childrenMode',[])
        if children:
            if len(children)==1 and children[0].get('modeType')==group.get('modeType'):
                children=[group]
            for child in children:
                if child.get('modeType') in MODES and 'protocolIndex' in child:
                    result['noise'].setdefault(MODES[child['modeType']],child['protocolIndex'])
        elif group.get('modeType') in MODES and 'protocolIndex' in group:
            result['noise'].setdefault(MODES[group['modeType']],group['protocolIndex'])
    presets={}
    for key in ('equalizerMode','equalizerModeCompat','equalizerModeByVersion'):
        for eq in f.get(key,[]):
            if 'protocolIndex' in eq:
                i=eq['protocolIndex']
                presets.setdefault(i,dict(id=i,name=NAMES.get(str(eq.get('modeType')),f'M{i}')))
    result['presets']=[presets[i] for i in sorted(presets)]
    return result

if __name__=='__main__':
    entries=json.loads((SOURCE/'DeviceModels.json').read_text('utf-8-sig'))['whiteList']
    models=[profile(x) for x in entries if x.get('brand','OPPO').casefold() in ('oppo','oneplus')]
    (ROOT/'encolite/oppo_models.json').write_text(json.dumps(models,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(f'Imported {len(models)} OPPO/OnePlus profiles')
