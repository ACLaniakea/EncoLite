"""OPPO/OnePlus identity and bounded service selection, with no Windows imports."""
import json,re
from functools import lru_cache
from pathlib import Path

MELODY='0000079a-d102-11e1-9b23-00025b00a5a5'
LEGACY='00001107-d102-11e1-9b23-00025b00a5a5'
EMPTY_SERVICE='00000000-0000-0000-0000-000000000000'

@lru_cache(maxsize=1)
def models():
    return json.loads(Path(__file__).with_name('oppo_models.json').read_text('utf-8'))

def is_candidate_name(name):
    return isinstance(name,str) and bool(re.search(r'(?<![a-z0-9])(?:oppo|enco|one\s*plus)(?![a-z0-9])|一加',name,re.I))

def is_earbud_candidate(name,device_class=0):
    """Headset CoD plus supported identity; model fallback for unspecified CoD.

    Class bits follow Bluetooth SIG Assigned Numbers, Audio/Video minor class.
    A phone/PC/speaker remains excluded even if renamed after a known earbud.
    """
    if not is_candidate_name(name):return False
    major=(device_class>>8)&0x1f;minor=(device_class>>2)&0x3f
    if major not in (0,4):return False
    if major==4 and minor not in (0,1,2,6):return False
    if major==4 and minor in (1,2,6):return True
    if model_for('',name.strip()):return True
    return bool(re.search(r'(?<![a-z0-9])(?:enco\s+\S|oppo\s+o[ -]?free\b|(?:one\s*plus|一加)\s+(?:(?:nord|open)\s+)?(?:buds\b|bullets\s*wireless\b)|一加\s*(?:云耳|银耳|耳机))',name,re.I))

def canonical_product_id(value):
    value=str(value or '').upper()
    if not re.fullmatch('[0-9A-F]{6}',value):return value
    number=int(value,16)
    for low,high,target in ((0x100100,0x100102,'060414'),(0x100200,0x100202,'060814'),
            (0x108100,0x108102,'068414'),(0x108200,0x108202,'068814')):
        if low<=number<=high:return target
    return value

def model_for(product_id,device_name=''):
    if product_id:
        identifier=canonical_product_id(product_id)
        return next((model for model in models() if model['id']==identifier or identifier in model.get('product_aliases',[])),None)
    name=str(device_name or '').strip().casefold()
    return next((model for model in models() if any(name==alias.casefold() for alias in [model['name'],*model.get('aliases',[])])),None)

def connection_attempts(name):
    profile=model_for('',name)
    # New devices use Melody; known older models advertise the alternate UUID.
    services=[MELODY]
    if profile and profile.get('service_uuid') in (MELODY,LEGACY):services.insert(0,profile['service_uuid'])
    if is_candidate_name(name):services.append(LEGACY)
    return tuple((service,0) for service in dict.fromkeys(services))+((EMPTY_SERVICE,1),(EMPTY_SERVICE,15))
