"""Implemented upstream OPPO controls, with capability gates and readback."""
from .oppo_features import (FEATURE_IDS, COMMAND_BITS, CustomEQ, parse_custom,
    custom_payload, parse_multi, multi_payload, parse_priority, parse_wear, parse_codec)


class ExtendedSession:
    def reset_extended(self):
        self.custom_entries=[]
        self.multi_devices=[]
        self.priority_address=None
        self.spatial_mode=None
        self.bass_state=None
        self.wear_state={}
        self.codec=''
        self.finding=False
        self.unavailable=set()
        self.dirty=set()

    def command_supported(self,command):
        from .live_session import bitmap_has
        return command in COMMAND_BITS and bitmap_has(self.bitmap,COMMAND_BITS[command])

    def supported(self,key):
        p=self.profile or {}
        if not self.connected or key in self.unavailable:
            return False
        both=lambda a,b:self.command_supported(a) and self.command_supported(b)
        if key in ('wear','dual','voice','long'):
            return bool(p.get(key)) and self.command_supported(0x0403)
        if key=='hearing':
            return bool(p.get(key)) and both(0x0115,0x040D) and self.command_supported(0x0403)
        if key=='spatial':
            return bool(p.get('spatial_types')) and self.command_supported(0x0403) and not both(0x012A,0x0422)
        if key=='spatial_audio':
            return bool(p.get('spatial_types')) and both(0x012A,0x0422)
        if key=='game':
            return bool(p.get('game')) and self.command_supported(0x0403)
        if key=='game_sound':
            return bool(p.get('game_types')) and both(0x012B,0x0423)
        if key=='bass':
            return bool(p.get('bass')) and both(0x0124,0x041B)
        if key=='custom':
            return bool(p.get('custom')) and both(0x0122,0x0418)
        if key=='multi':
            return bool(p.get('multi')) and self.command_supported(0x0112)
        if key=='multi_write':
            return self.supported('multi') and self.command_supported(0x0429)
        if key=='find':
            return bool(p.get('find')) and self.command_supported(0x0400)
        return False

    def feature_id(self,key):
        if key=='game':
            if self.supported('game_sound') and 0x28 in self.features:
                return 0x28
            return 6 if 6 in self.features else 0x28
        return FEATURE_IDS.get(key)

    def feature_value(self,key):
        if key=='bass':
            return bool(self.bass_state and self.bass_state[2]!=self.bass_state[0])
        return self.features.get(self.feature_id(key),False)

    def feature_available(self,key):
        return self.supported(key) and (self.bass_state is not None if key=='bass' else self.feature_id(key) in self.features)

    def feature_query(self):
        ids=[5,6,0x28]
        ids.extend(value for key,value in FEATURE_IDS.items() if self.supported(key))
        if self.supported('game_sound'):
            ids.append(0x27)
        return bytes((len(ids),*ids))

    def extended_receive(self,command,data):
        if command==0x8122:
            self.custom_entries=parse_custom(data)
        elif command==0x8112:
            self.multi_devices=parse_multi(data)
        elif command==0x8132:
            self.priority_address=parse_priority(data)
        elif command==0x812A and len(data)>=2 and data[1] in (0,1,2):
            self.spatial_mode=data[1]
        elif command==0x8124 and len(data)>=4 and data[1]<=data[3]<=data[2]:
            self.bass_state=tuple(data[1:4])
        elif command==0x8109:
            self.wear_state.update(parse_wear(data))
        elif command==0x8114:
            self.codec=parse_codec(data)
        else:
            return False
        return True

    def extended_refresh(self):
        # Explicit refusal disables only that optional function for this session.
        # A timeout still closes the link to avoid matching delayed responses.
        for key,command,payload in (
            ('spatial_audio',0x012A,b''),('bass',0x0124,b''),
            ('custom',0x0122,b'\x01\x05'),('multi',0x0112,b'')):
            if self.supported(key):
                try:
                    self.request(command,payload)
                except ValueError:
                    self.unavailable.add(key)
        if self.supported('multi') and self.command_supported(0x0132):
            self.request(0x0132)
        for command in (0x0109,0x0114):
            if self.command_supported(command):
                self.request(command)

    def _settle(self):
        if self.cancel.wait(.15):
            raise ConnectionAbortedError('操作已取消')

    def _verify(self,actual,expected):
        if actual!=expected:
            raise ValueError('耳机未应用该设置，已显示实际状态')

    def set_feature(self,key,enabled):
        if not self.feature_available(key):
            raise ValueError('耳机不支持该开关')
        enabled=bool(enabled)
        if key=='bass':
            low,high,_=self.bass_state
            target=high if enabled else low
            self.request(0x041B,bytes((low,high,target)))
            self._settle(); self.request(0x0124)
            self._verify(self.bass_state[2],target)
            return
        if key=='spatial' and enabled and self._blocks('spatial') and self.game_sound:
            self.set_game_sound(0)
        self.request(0x0403,bytes((self.feature_id(key),int(enabled))))
        self._settle(); self.request(0x010D,self.feature_query())
        self._verify(self.feature_value(key),enabled)

    def _blocks(self,target):
        mutex=set((self.profile or {}).get('mutex',[]))
        return bool(mutex & ({1,3} if target=='eq' else {2,3}))

    def set_spatial(self,mode):
        if not self.supported('spatial_audio') or mode not in (0,1,2) or mode not in self.profile.get('spatial_types',[]):
            raise ValueError('耳机不支持该空间音频模式')
        if mode and self._blocks('spatial') and self.game_sound:
            self.set_game_sound(0)
        self.request(0x0422,bytes((mode,)))
        self._settle(); self.request(0x012A)
        self._verify(self.spatial_mode,mode)

    def set_game_sound(self,value):
        if not self.supported('game_sound') or value not in {0,*self.profile.get('game_types',[])}:
            raise ValueError('耳机不支持该游戏音效')
        if value:
            if self._blocks('spatial'):
                if self.supported('spatial_audio') and self.spatial_mode:
                    self.set_spatial(0)
                elif self.feature_available('spatial') and self.feature_value('spatial'):
                    self.set_feature('spatial',False)
            if self._blocks('eq') and self.preset!=0:
                self.set_preset(0)
        self.request(0x0423,bytes((value,1)))
        self._settle(); self.request(0x012B)
        self._verify(self.game_sound,value)

    def find_device(self,enabled):
        if not self.supported('find'):
            raise ValueError('耳机不支持查找功能')
        self.request(0x0400,bytes((int(bool(enabled)),)))
        self.finding=bool(enabled)
        self._changed()

    def write_custom(self,action,entry):
        if not self.supported('custom'):
            raise ValueError('耳机不支持自定义均衡器')
        if tuple(self.profile['frequencies'])!=entry.frequencies:
            raise ValueError('频段必须与耳机型号一致')
        if action in (2,3) and not any(e.id==entry.id for e in self.custom_entries):
            raise ValueError('所选音效已不存在，请刷新')
        maximum=self.profile.get('custom_max',0)
        if action==1 and maximum>0 and len(self.custom_entries)>=maximum:
            raise ValueError('耳机自定义音效数量已达上限')
        if action!=3 and any(e.name==entry.name and e.id!=entry.id for e in self.custom_entries):
            raise ValueError('已有同名音效，请更换名称')
        if action!=3 and not self.eq_available:
            if self.game_sound and self._blocks('eq'):
                self.set_game_sound(0)
            else:
                raise ValueError('当前无法编辑均衡器')
        self.request(0x0418,custom_payload(action,entry))
        self._settle(); self.request(0x0122,b'\x01\x05')
        if action==3:
            self._verify(any(e.id==entry.id for e in self.custom_entries),False)
            self.request(0x010F)
            return
        actual=next((e for e in self.custom_entries if e.name==entry.name),None)
        if actual is None or actual.frequencies!=entry.frequencies or actual.gains!=entry.gains:
            raise ValueError('自定义音效回读与保存内容不一致')
        self.set_preset(actual.id)
        return actual

    def operate_multi(self,action,address=''):
        if not self.supported('multi_write'):
            raise ValueError('耳机不支持设备连接操作')
        if action!='auto' and not any(d['address']==address for d in self.multi_devices):
            raise ValueError('设备列表已变化，请刷新')
        self.request(0x0429,multi_payload(action,address))
        self._settle(); self.request(0x0112)
        if self.command_supported(0x0132):
            self.request(0x0132)
        actual=next((d for d in self.multi_devices if d['address']==address),None)
        if action=='connect':
            self._verify(actual is not None and actual['state']==2,True)
        elif action=='disconnect':
            self._verify(actual is None or actual['state']!=2,True)
        elif action=='unpair':
            self._verify(actual is None,True)
        elif self.command_supported(0x0132):
            self._verify(self.priority_address,None if action=='auto' else address)

    def select_model(self,identifier):
        from .live_session import model_for
        profile=model_for(identifier,'')
        if profile is None:
            raise ValueError('未知耳机型号')
        self.profile=profile
        self.device_name=profile['name']
        self.reset_extended()
        self.refresh()
