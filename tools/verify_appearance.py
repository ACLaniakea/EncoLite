"""Actual renderer and window lifecycle checks with isolated local preferences."""
from pathlib import Path
import ctypes as C,json,os,sys,traceback
from ctypes import wintypes as W
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
data=ROOT/'.install-test/appearance';data.mkdir(parents=True,exist_ok=True)
os.environ['ENCOLITE_DATA_DIR']=str(data)
from encolite.web_desktop import Desktop
from encolite.webview_native import Handler,call,checked,HRESULT
from encolite.controller import Controller
from encolite.session import DemoSession
from encolite import windows_shell as shell
shell.user.SetProcessDpiAwarenessContext(C.c_void_p(-4))
preferences=data/'preferences.json';preferences.unlink(missing_ok=True)
controller=Controller(session=DemoSession(),preferences=preferences)
app=Desktop(ROOT);report={'checks':[],'errors':[]};messages=[]
folder=ROOT/'verification/appearance';folder.mkdir(parents=True,exist_ok=True)
base={'model_name':'OPPO Enco X3','connected':True,'status':'已连接','busy':False,
    'switches':[{'key':'wear','title':'佩戴检测','detail':'摘下暂停，戴上继续','checked':False,'enabled':True}]}

def publish():
    state={**base,**{key:getattr(controller,key) for key in ('dark','theme_mode','fast_mode','system_dark','system_motion','connection_popup')}}
    app.receive({'type':'state','fixture':True,'preferences':controller.preference_data,'state':state})

def send(kind,**values):
    messages.append({'type':kind,**values})
    if kind=='action':
        name=values['name'];args=values['args']
        if name in ('change_theme_mode','change_fast_mode','change_connection_popup'):
            getattr(controller,name)(*args);publish()
        elif name=='change_feature':
            base.update(busy=True,status_error=False);publish()
        elif name=='save_window':pass
app.send=send

def fail(error):report['errors'].append(str(error));app.quit()
def check(label):report['checks'].append(label);print('PASS',label,flush=True)
def execute(script,callback,kind='main'):
    def completed(status,value):
        try:checked(status);callback(json.loads(value))
        except Exception:fail(traceback.format_exc())
    handler=Handler('49511172-CC67-4BCA-9923-137112F4C4CC',completed,(HRESULT,W.LPCWSTR))
    window=app.windows[kind];window.browser.handlers.append(handler)
    checked(call(window.browser.core,29,script,handler.pointer,types=(W.LPCWSTR,C.c_void_p)))

def start():
    script='''(()=>{
      navigatePage(2);
      const theme=document.querySelector('[data-select="theme"]');
      const selected=theme.value;
      Object.defineProperty(colorMedia,'matches',{configurable:true,value:true});
      colorMedia.dispatchEvent(new Event('change'));const dark=document.documentElement.classList.contains('dark');
      Object.defineProperty(colorMedia,'matches',{configurable:true,value:false});
      colorMedia.dispatchEvent(new Event('change'));const light=!document.documentElement.classList.contains('dark');
      delete colorMedia.matches;applyAppearance();
      theme.value='dark';theme.dispatchEvent(new Event('change',{bubbles:true}));
      return {selected,dark,light};
    })()'''
    def result(value):
        assert value=={'selected':'system','dark':True,'light':True},value
        check('system appearance events update the UI without changing Windows settings')
        app.later(.15,manual)
    execute(script,result)

def manual():
    assert controller.theme_mode=='dark'
    def result(value):
        assert value['dark'] and value['mode']=='dark',value
        check('manual theme selection reaches the controller and persists')
        app.windows['main'].browser.capture(folder/'settings-dark.png',lambda:app.later(.1,fast))
    execute("({dark:document.documentElement.classList.contains('dark'),mode:document.querySelector('[data-select=theme]').value})",result)

def fast():
    execute("(()=>{document.querySelector('[data-switch=fast_mode]').click();return true})()",lambda _:app.later(.1,verify_fast))

def verify_fast():
    assert controller.fast_mode
    script='''(()=>{
      const oldNav=document.querySelector('.nav');navigatePage(4);
      const value={sameNav:oldNav===document.querySelector('.nav'),fast:document.documentElement.classList.contains('fast-mode'),
        transition:getComputedStyle(document.querySelector('.switch'),'::after').transitionDuration,
        shadow:getComputedStyle(document.querySelector('.card')).boxShadow,
        animations:document.getAnimations().filter(x=>x.playState==='running').length};
      document.querySelector('[data-switch=wear]').click();return value;
    })()'''
    def result(value):
        assert value=={'sameNav':True,'fast':True,'transition':'0s','shadow':'none','animations':0},value
        check('speed mode removes transitions, shadows and running animations; navigation reuses the sidebar')
        app.later(.06,pending)
    execute(script,result)

def pending():
    def result(value):
        assert value, 'device acknowledgement rolled the switch back prematurely'
        base.update(busy=False,status_error=True);publish()
        app.later(.1,rejected)
    execute("document.querySelector('[data-switch=wear]').checked",result)

def rejected():
    def result(value):
        assert value is False
        check('pending switch remains stable until device completion, then reflects rejection')
        execute("(()=>{navigatePage(2);document.querySelector('[data-switch=fast_mode]').click();return true})()",lambda _:app.later(.12,reduced))
    execute("document.querySelector('[data-switch=wear]').checked",result)

def reduced():
    assert not controller.fast_mode
    script='''(()=>{
      Object.defineProperty(reducedMotionMedia,'matches',{configurable:true,value:true});
      reducedMotionMedia.dispatchEvent(new Event('change'));
      const disabled=!motionEnabled()&&document.documentElement.classList.contains('motion-off');
      delete reducedMotionMedia.matches;applyAppearance();return disabled;
    })()'''
    def result(value):
        assert value
        check('reduced motion preference disables motion independently of speed mode')
        data=json.loads(preferences.read_text('utf-8'))
        assert data['theme_mode']=='dark' and data['fast_mode'] is False
        check('appearance and speed settings persist independently')
        switch()
    execute(script,result)

def switch():
    main=app.windows['main'];app.show('quick')
    assert not main.closed,'source closed before the destination was ready'
    def ready():
        def finished():
            assert main.closed and 'main' not in app.windows
            assert app.windows['quick'].ready
            check('window switching retains the source until the destination renders and releases it afterwards')
            reopen()
        app.later(.3,finished)
    app.when_ready('quick',ready)

def reopen():
    window=app.windows['quick']
    if window.motion_enabled:
        window.close(exiting=False);token=window.close_serial
        assert window.closing
        app.show('quick');assert not window.closing
        app.window_message(window,{'type':'window','name':'dismissed','token':token})
        assert not window.closed
        check('reopening cancels dismissal and ignores an old animation completion')
    else:check('system reduced motion uses the immediate window path')
    app.later(.2,fallback)

def fallback():
    window=app.windows['quick'];original=window.browser.send
    window.browser.send=lambda message:None if message.get('type')=='dismiss' else original(message)
    window.close(exiting=False)
    def finished():
        assert window.closed,'renderer blocked cleanup'
        check('window cleanup is bounded even without an animation acknowledgement')
        app.show('notice');app.when_ready('notice',notice)
    app.later(.35,finished)

def notice():
    window=app.windows['notice'];window.notice_timeout(False,.08)
    def hover():
        if window.closed:return fail('notice closed before its hover grace interval')
        window.notice_timeout(True)
        assert not window.closing
        def finished():
            assert not window.closed
            check('connection notice hover cancels expiry or its closing transition')
            tray=object.__new__(shell.Tray);tray.taskbar_created=0xFFFF
            deferred=[];tray.defer=deferred.append;tray.on_settings_changed=lambda:None
            tray._wndproc(None,0x1A,0,0);tray._wndproc(None,0x31A,0,0)
            assert deferred==[tray.on_settings_changed,tray.on_settings_changed]
            check('native system setting broadcasts schedule event-driven updates')
            app.quit()
        app.later(.3,finished)
    # If animations are disabled there is no dismissal grace interval to hover into.
    app.later(.1 if window.motion_enabled else .04,hover)

publish();app.show('main');app.when_ready('main',lambda:app.later(.25,start));app.later(30,lambda:fail('appearance verification timeout'))
try:app.loop.run()
finally:
    app.quit();controller.close()
    if app.environment:app.environment.close()
    shell.DestroyWindow(app.owner)
    report['result']='FAIL' if report['errors'] else 'PASS'
    (folder/'report.json').write_text(json.dumps(report,indent=2),'utf-8')
    print(json.dumps(report),flush=True)
    if report['errors']:raise SystemExit(1)
