"""Compact feature pages share the same serialized Bluetooth session."""
import json
from pathlib import Path
from .oppo_features import (FEATURE_TITLES,FEATURE_DETAILS,NOISE_TITLES,CustomEQ)

class AdvancedController:
    def init_advanced(self):
        self._types=None
        self._advanced_models={}
        self._draft_id=0
        self._draft_name='我的音效'
        self._draft_frequencies=()
        self._draft_gains=[]
        self._draft_min=-6
        self._draft_max=6
        self._custom_index=0
        self._profile_id=None
        self._model_profiles=json.loads(Path(__file__).with_name('oppo_models.json').read_text('utf-8'))
        self._model_profiles.sort(key=lambda p:p['name'])

    def list_model(self,key,values,typename=None):
        signature=repr(values)
        previous=self._advanced_models.get(key)
        if previous and previous[0]==signature:
            return previous[1]
        model=self.presentation.model(values,typename)
        self._advanced_models[key]=(signature,model)
        return model

    def sync_advanced(self,w):
        s=self.session
        if not hasattr(w,'switches'):
            return
        live=self.live
        profile=s.profile if live else None
        identity=profile['id'] if profile else None
        if identity!=self._profile_id:
            self._profile_id=identity
            self._load_custom(0)
        switches=[]
        if live:
            for key in ('wear','dual','game','voice','hearing','long','bass','spatial'):
                if s.supported(key):
                    switches.append(dict(key=key,title=FEATURE_TITLES[key],detail=FEATURE_DETAILS[key],checked=s.feature_value(key),enabled=s.feature_available(key)))
        w.switches=self.list_model('switches',switches,'SwitchItem')
        modes=s.noise_modes if live else {'off':0,'transparency':8,'vocal':9,'smart':7,'light':6,'moderate':5,'deep':4}
        w.noise_options=self.list_model('noise',[dict(key=k,name=NOISE_TITLES[k]) for k in NOISE_TITLES if k in modes],'NoiseItem')
        w.spatial_visible=live and s.supported('spatial_audio')
        w.spatial_mode=s.spatial_mode if live and s.spatial_mode is not None else -1
        spatial=[dict(id=i,name={0:'关闭',1:'固定空间',2:'头部跟踪'}[i],detail='') for i in (profile or {}).get('spatial_types',[]) if i in (0,1,2)] if w.spatial_visible else []
        w.spatial_options=self.list_model('spatial',spatial,'PresetItem')
        game_types=sorted(set([0,*(profile or {}).get('game_types',[])])) if live and s.supported('game_sound') else []
        w.game_options=self.list_model('game',[dict(id=i,name='关闭' if i==0 else '游戏音效' if len(game_types)==2 else f'音效 {i}',detail='') for i in game_types],'PresetItem')
        w.game_type=s.game_sound if live and s.game_sound is not None else -1
        w.find_visible=live and s.supported('find')
        w.finding=live and s.finding
        w.device_info=' · '.join(filter(None,([s.firmware,s.codec,'左耳'+s.wear_state[1] if 1 in s.wear_state else '', '右耳'+s.wear_state[2] if 2 in s.wear_state else ''] if live else [])))
        w.custom_available=live and s.supported('custom')
        entries=s.custom_entries if live else []
        # A remote deletion invalidates the editor selection rather than targeting a new row.
        if self._draft_id and not any(e.id==self._draft_id for e in entries):
            self._load_custom(0)
        self._custom_index=next((i+1 for i,e in enumerate(entries) if e.id==self._draft_id),0)
        w.custom_names=self.list_model('custom_names',['新增音效',*(e.name for e in entries)])
        w.custom_index=self._custom_index
        w.eq_name=self._draft_name
        w.eq_minimum=self._draft_min
        w.eq_maximum=self._draft_max
        w.bands=self.list_model('bands',[dict(label=f'{f/1000:g} kHz' if f>=1000 else f'{f} Hz',gain=g) for f,g in zip(self._draft_frequencies,self._draft_gains)],'BandItem')
        w.multi_available=live and s.supported('multi')
        w.multi_writable=live and s.supported('multi_write')
        devices=[dict(address=d['address'],name=d['name'],detail=('已连接' if d['state']==2 else '未连接')+(' · 此电脑' if d['current'] else '')+(' · 优先设备' if d['priority'] else ''),connected=d['state']==2) for d in (s.multi_devices if live else []) if d['address']!='00:00:00:00:00:00']
        w.multi_devices=self.list_model('multi',devices,'DeviceItem')
        w.priority_text=('优先连接：'+s.priority_address if live and s.priority_address else '管理耳机的设备连接')
        w.model_names=self.list_model('models',[p['name'] for p in self._model_profiles])
        w.model_index=next((i for i,p in enumerate(self._model_profiles) if p['id']==identity),-1)

    def _load_custom(self,index):
        s=self.session
        entries=s.custom_entries if self.live else []
        entry=entries[index-1] if 0<index<=len(entries) else None
        self._custom_index=index if entry else 0
        self._draft_id=entry.id if entry else 0
        self._draft_name=entry.name if entry else '我的音效'
        self._draft_frequencies=tuple((s.profile or {}).get('frequencies',[])) if self.live else (62,250,1000,4000,8000,16000)
        gains=dict(zip(entry.frequencies,entry.gains)) if entry else {}
        self._draft_gains=[gains.get(f,0) for f in self._draft_frequencies]
        self._draft_min=entry.minimum if entry else -6
        self._draft_max=entry.maximum if entry else 6

    def select_custom(self,index):
        if not self.busy:
            self._load_custom(index)
            self.sync()

    def edit_custom_name(self,value):
        self._draft_name=value

    def edit_gain(self,index,value):
        if not self.busy and 0<=index<len(self._draft_gains):
            self._draft_gains[index]=max(self._draft_min,min(self._draft_max,value))
            self.sync()

    def write_custom(self,action):
        if not self.live or action not in ('save','preview','delete'):
            return
        entry=CustomEQ(self._draft_id,self._draft_name,tuple(self._draft_frequencies),tuple(self._draft_gains),self._draft_min,self._draft_max)
        operation=3 if action=='delete' else 2 if self._draft_id else 1
        if action=='preview' and not self._draft_id:
            self.set_status('请先保存音效，再试听修改')
            return
        def completed(saved):
            if saved:
                self._draft_id=saved.id
            elif action=='delete':
                self._load_custom(0)
            self.sync()
        self.perform(lambda:self.session.write_custom(operation,entry),'音效已删除' if operation==3 else '音效已保存并启用',then=completed)

    def change_spatial(self,value):
        if self.live:
            self.perform(lambda:self.session.set_spatial(value),'空间音频已更新')

    def change_game(self,value):
        if self.live:
            self.perform(lambda:self.session.set_game_sound(value),'游戏音效已更新')

    def find_device(self,enabled):
        if self.live:
            self.perform(lambda:self.session.find_device(enabled),'正在播放提示音' if enabled else '提示音已停止')

    def operate_multi(self,action,address):
        if self.live:
            self.perform(lambda:self.session.operate_multi(action,address),'设备连接已更新')

    def select_model(self,index):
        if self.live and 0<=index<len(self._model_profiles):
            self.perform(lambda:self.session.select_model(self._model_profiles[index]['id']),'已更新耳机型号')
