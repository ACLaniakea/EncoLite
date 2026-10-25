"""OPPO feature payloads adapted from OppoPodsManager, GPL-3.0-or-later.

Pure parsers reject incomplete replies atomically. Addresses follow upstream:
list responses use reversed octets, operation requests use displayed order.
"""
from dataclasses import dataclass
import re
import struct

FEATURE_IDS={'wear':4,'dual':0x11,'voice':9,'hearing':0x0B,'long':0x17,'spatial':0x1B}
FEATURE_TITLES={'wear':'佩戴检测','dual':'双设备连接','voice':'人声增强','hearing':'听力增强','long':'长续航模式','spatial':'空间音效','game':'游戏模式','bass':'低音引擎'}
FEATURE_DETAILS={'wear':'摘下暂停，戴上继续','dual':'同时连接两台设备','voice':'突出音乐中的人声','hearing':'使用耳机已保存的听力设置','long':'以音质设置换取更长续航','spatial':'更有空间感的聆听','game':'减少游戏音频延迟','bass':'增强低频表现'}
NOISE_TITLES={'off':'关闭','transparency':'通透','vocal':'人声通透','smart':'智能降噪','light':'轻度降噪','moderate':'中度降噪','deep':'深度降噪','adaptive':'自适应','nc':'降噪'}
COMMAND_BITS={0x0105:0,0x0109:4,0x0400:5,0x0403:7,0x010C:8,0x0404:8,0x010F:10,0x0406:10,0x0114:17,0x0115:19,0x040D:19,0x0205:22,0x0112:29,0x0122:34,0x0418:34,0x0124:38,0x041B:38,0x012A:47,0x0422:47,0x012B:49,0x0423:49,0x0132:59,0x0429:59}

@dataclass(frozen=True)
class CustomEQ:
    id:int
    name:str
    frequencies:tuple
    gains:tuple
    minimum:int=-6
    maximum:int=6
    selected:bool=False


def parse_custom(data):
    if len(data)<2 or data[0]!=0:
        raise ValueError('自定义均衡器响应无效')
    result=[]; pos=2
    for _ in range(data[1]):
        if pos+5>len(data):
            raise ValueError('自定义均衡器条目不完整')
        selected,low,high,identifier,length=data[pos:pos+5]; pos+=5
        if pos+length+1>len(data):
            raise ValueError('自定义均衡器名称不完整')
        name=data[pos:pos+length].decode('utf-8').rstrip('\0'); pos+=length
        count=data[pos]; pos+=1
        if pos+count*3>len(data):
            raise ValueError('自定义均衡器频段不完整')
        bands=[struct.unpack_from('<Hb',data,pos+i*3) for i in range(count)]; pos+=count*3
        result.append(CustomEQ(identifier,name,tuple(b[0] for b in bands),tuple(b[1] for b in bands),low-256 if low>127 else low,high-256 if high>127 else high,bool(selected)))
    return result


def custom_payload(action,entry):
    if action not in (1,2,3) or not entry.frequencies or len(entry.frequencies)!=len(entry.gains):
        raise ValueError('均衡器频段无效')
    if action!=3 and not re.fullmatch(r'[a-zA-Z0-9\u4e00-\u9fa5]+',entry.name):
        raise ValueError('名称仅可使用中文、字母和数字')
    name=entry.name.encode('utf-8')
    if len(name)>255 or len(entry.frequencies)>255 or not 0<=entry.id<=255:
        raise ValueError('均衡器条目过长')
    if not -128<=entry.minimum<=entry.maximum<=127 or any(not entry.minimum<=g<=entry.maximum for g in entry.gains):
        raise ValueError('增益超出耳机允许范围')
    payload=bytes((action,entry.minimum&255,entry.maximum&255,entry.id,len(name)))+name+bytes((len(entry.frequencies),))+b''.join(struct.pack('<Hb',f,g) for f,g in zip(entry.frequencies,entry.gains))
    if len(payload)>248:
        raise ValueError('均衡器条目超过协议长度')
    return payload


def parse_multi(data):
    if len(data)<2 or data[0]:
        raise ValueError('设备列表响应无效')
    result=[]; pos=2
    for _ in range(data[1]):
        if pos+10>len(data):
            raise ValueError('设备列表不完整')
        address=':'.join(f'{x:02X}' for x in reversed(data[pos:pos+6])); pos+=6
        kind,state,flags,length=data[pos:pos+4]; pos+=4
        if pos+length>len(data):
            raise ValueError('设备名称不完整')
        name=data[pos:pos+length].decode('utf-8','replace').rstrip('\0'); pos+=length
        result.append(dict(address=address,name=name or address,type=kind,state=state,current=bool(flags&1),priority=bool(flags&4),remote=bool(flags&2)))
    return result


def multi_payload(action,address=''):
    if action=='auto':
        return b'\x04\x00'
    if action not in ('connect','disconnect','unpair','priority') or not re.fullmatch(r'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}',address):
        raise ValueError('设备操作或地址无效')
    raw=bytes.fromhex(address.replace(':',''))
    return (b'\x04\x01' if action=='priority' else bytes(({'connect':1,'disconnect':2,'unpair':3}[action],)))+raw


def parse_priority(data):
    if len(data)>=3 and data[0]==0:
        data=data[1:]
    if len(data)<2 or data[0] not in (1,2):
        raise ValueError('连接优先级响应无效')
    return None if data[1]==0 or len(data)<8 else ':'.join(f'{x:02X}' for x in reversed(data[2:8]))


def parse_wear(data):
    if data and data[0]==0:
        data=data[1:]
    if len(data)%2 and data and len(data)>=1+data[0]*2:
        data=data[1:1+data[0]*2]
    names={0:'未连接',1:'未佩戴',5:'未佩戴',3:'已佩戴',7:'已佩戴',4:'在盒中'}
    return {data[i]:names.get(data[i+1],'未知') for i in range(0,len(data)-1,2) if data[i] in (1,2)}


def parse_codec(data):
    if len(data)<2 or data[0]:
        return ''
    names={0:'SBC',1:'LDAC',2:'AAC',3:'LHDC',4:'LC3',8:'LHDC'}
    if len(data)==2:
        return names.get(data[1],f'Codec {data[1]}')
    if len(data)<2+data[1]*2:
        return ''
    return next((names.get(data[i],f'Codec {data[i]}') for i in range(2,2+data[1]*2,2) if data[i+1]),'')
