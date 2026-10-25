"""Event-driven global shortcuts. Registration and settings are independent of GUI lifetime."""
from copy import deepcopy

ACTIONS=(('toggle_noise','降噪 / 通透切换'),('show_quick','打开快捷控制'),
         ('show_main','打开主窗口'),('noise_off','关闭降噪与通透'),('next_preset','切换下一音效'))
DEFAULTS={'toggle_noise':{'modifiers':3,'key':ord('N')},'show_quick':{'modifiers':3,'key':ord('Q')}}
KEY_NAMES={32:'Space',33:'PageUp',34:'PageDown',35:'End',36:'Home',37:'←',38:'↑',39:'→',40:'↓',45:'Insert',46:'Delete'}
KEY_NAMES.update({key:chr(key) for key in range(48,58)})
KEY_NAMES.update({key:chr(key) for key in range(65,91)})
KEY_NAMES.update({111+n:f'F{n}' for n in range(1,25) if n!=12})


def binding(value):
    if value is None:return None
    if (not isinstance(value,dict) or set(value)!={'modifiers','key'} or
            type(value['modifiers']) is not int or type(value['key']) is not int):
        raise ValueError('快捷键格式无效')
    modifiers,key=value['modifiers'],value['key']
    if modifiers<1 or modifiers>7 or not modifiers&3:
        raise ValueError('请包含 Ctrl 或 Alt，且不使用 Win 键')
    if key not in KEY_NAMES:raise ValueError('请选择字母、数字、方向键或功能键；F12 为系统保留键')
    if (modifiers,key) in {(1,115),(3,46)}:raise ValueError('这个组合由系统保留')
    return {'modifiers':modifiers,'key':key}


def label(value):
    if value is None:return '未设置'
    return ' + '.join([name for mask,name in ((2,'Ctrl'),(1,'Alt'),(4,'Shift')) if value['modifiers']&mask]+[KEY_NAMES[value['key']]])


def saved_config(value):
    value=value if isinstance(value,dict) else {}
    enabled=value.get('enabled',True);enabled=enabled if type(enabled) is bool else True
    saved=value.get('bindings');saved=saved if isinstance(saved,dict) else {}
    bindings={};seen=set()
    for action,_ in ACTIONS:
        try:current=binding(saved.get(action,deepcopy(DEFAULTS.get(action))))
        except ValueError:current=None
        identity=(current['modifiers'],current['key']) if current else None
        if identity in seen:current=None
        if current:seen.add(identity)
        bindings[action]=current
    return {'enabled':enabled,'bindings':bindings}


class WindowsRegistration:
    def __init__(self,hwnd):
        import ctypes as C
        from ctypes import wintypes as W
        from .windows_shell import api,user
        self.hwnd=hwnd
        self.register_api=api(user,'RegisterHotKey',W.BOOL,W.HWND,C.c_int,W.UINT,W.UINT)
        self.unregister_api=api(user,'UnregisterHotKey',W.BOOL,W.HWND,C.c_int)

    def register(self,identifier,value):
        return bool(self.register_api(self.hwnd,identifier,value['modifiers']|0x4000,value['key']))

    def unregister(self,identifier):self.unregister_api(self.hwnd,identifier)


class Hotkeys:
    def __init__(self,registration,config,save,activate):
        self.registration,self.save,self.activate=registration,save,activate
        self.config=saved_config(config);self.active={};self.errors={};self.suspended=False;self.closed=False;self.slots={}
        self._register_all()

    def _identifier(self,action):
        base=0x5200+2*[key for key,_ in ACTIONS].index(action)
        return base+int(self.slots.get(action)==base)

    def _register_all(self):
        if not self.config['enabled'] or self.suspended or self.closed:return
        self.errors={}
        for action,value in self.config['bindings'].items():
            if not value:continue
            identifier=self._identifier(action)
            if self.registration.register(identifier,value):
                self.active[action]=(identifier,deepcopy(value));self.slots[action]=identifier
            else:self.errors[action]='已被其他应用占用或被系统保留'

    def _release(self):
        for identifier,_ in self.active.values():self.registration.unregister(identifier)
        self.active.clear()

    def snapshot(self):
        return {'enabled':self.config['enabled'],'capturing':self.suspended,
            'items':[{'action':action,'title':title,'binding':deepcopy(self.config['bindings'][action]),
                'label':label(self.config['bindings'][action]),'active':action in self.active,
                'error':self.errors.get(action,'')} for action,title in ACTIONS]}

    def set_binding(self,action,value):
        if self.closed:raise ValueError('快捷键服务已退出')
        if action not in self.config['bindings']:raise ValueError('未知的快捷键操作')
        value=binding(value)
        for other,current in self.config['bindings'].items():
            if value and other!=action and value==current:
                raise ValueError('已用于“'+dict(ACTIONS)[other]+'”')
        if value==self.config['bindings'][action] and action in self.active:return
        candidate=None
        if value and self.config['enabled']:
            candidate=self._identifier(action)
            if not self.registration.register(candidate,value):raise ValueError('此快捷键已被其他应用占用或被系统保留')
        updated=deepcopy(self.config);updated['bindings'][action]=value
        try:self.save(updated)
        except Exception:
            if candidate is not None:self.registration.unregister(candidate)
            raise
        old=self.active.pop(action,None)
        if old:self.registration.unregister(old[0])
        self.config=updated;self.errors.pop(action,None)
        if candidate is not None:
            self.slots[action]=candidate
            if self.suspended:self.registration.unregister(candidate)
            else:self.active[action]=(candidate,deepcopy(value))

    def set_enabled(self,enabled):
        if type(enabled) is not bool:raise ValueError('快捷键开关无效')
        if enabled==self.config['enabled']:return
        updated=deepcopy(self.config);updated['enabled']=enabled
        self.save(updated);self._release();self.config=updated;self.errors={};self._register_all()

    def suspend(self):
        if self.suspended:return
        self.suspended=True;self._release()

    def resume(self):
        if not self.suspended:return
        self.suspended=False;self._register_all()

    def handle(self,identifier,packed):
        if self.closed or self.suspended or not self.config['enabled']:return False
        for action,(registered,value) in self.active.items():
            if registered==identifier and (packed&0xFFFF)==value['modifiers'] and ((packed>>16)&0xFFFF)==value['key']:
                self.activate(action);return True
        return False

    def close(self):self.closed=True;self._release()


def execute_shortcut(controller,action,show):
    if action in ('show_main','show_quick'):
        show('main' if action=='show_main' else 'quick');return
    if controller.busy or controller.connecting:return
    session=controller.session
    if not session.connected or not getattr(session,'ready',True):
        controller.set_status('请先连接耳机');controller.sync();return
    if action=='next_preset':
        if controller._presets():controller.next_preset()
        else:controller.set_status('此耳机暂无可切换的音效');controller.sync()
        return
    modes=session.noise_modes if controller.live else ('smart','light','moderate','deep','transparency','off')
    if action=='toggle_noise':
        anc=controller.anc_level
        if anc not in modes or anc in ('off','transparency','vocal'):
            anc=next((mode for mode in modes if mode not in ('off','transparency','vocal')),None)
        transparency='transparency' if 'transparency' in modes else 'vocal' if 'vocal' in modes else None
        if not anc or not transparency:
            controller.set_status('此耳机不支持降噪与通透切换');controller.sync();return
        controller.change_noise(anc if session.noise in ('off','transparency','vocal') else transparency)
    elif action=='noise_off':
        if 'off' in modes:controller.change_noise('off')
        else:controller.set_status('此耳机不支持关闭聆听模式');controller.sync()
