"""Native frameless windows with a local HTML/CSS interface and no HTTP server."""
from pathlib import Path
import base64,ctypes as C,json,os,sys,threading,time,traceback
from ctypes import wintypes as W
from . import windows_shell as s
from .native_loop import NativeLoop
from .preferences import data_directory,window_state,fit_bounds
from .webview_native import Environment,Browser,call

TITLES={'main':'Enco Lite · 耳机助手','quick':'Enco Lite · 快捷控制','notice':'Enco Lite · 连接提示'}


class MinMaxInfo(C.Structure):
    _fields_=[('reserved',W.POINT),('max_size',W.POINT),('max_position',W.POINT),('min_track',W.POINT),('max_track',W.POINT)]


class Desktop:
    def __init__(self,root):
        self.root=root;self.loop=NativeLoop();self.windows={};self.handles={};self.environment=None
        self.payload={'type':'state','state':{},'preferences':{}};self.stopping=False;self.picture_key=None;self.picture_data=''
        self.test_id=None;self.test_stage=None;self.test_diagnostic=None
        sys.stdin.reconfigure(encoding='utf-8');sys.stdout.reconfigure(encoding='utf-8')
        self.procedure=s.WNDPROC(self.wndproc)
        self.kind=s.WndClass(name='EncoLiteWebWindow',proc=self.procedure,instance=s.GetModuleHandle(None),background=C.c_void_p(6))
        if not s.RegisterClass(C.byref(self.kind)):raise C.WinError(C.get_last_error())
        self.owner=s.CreateWindow(0,self.kind.name,'Enco Lite interface owner',0,0,0,0,0,None,None,self.kind.instance,None)
        if not self.owner:raise C.WinError(C.get_last_error())
        self.loop.hwnd=self.owner
        folder=root/'ui/web'
        self.html=(folder/'index.html').read_text('utf-8').replace('/*__STYLE__*/',(folder/'style.css').read_text('utf-8')).replace('/*__SCRIPT__*/',(folder/'app.js').read_text('utf-8'))
        self.pending_views=[];self.callbacks=[];self.retired=[];self.requested_view=None

    def later(self,seconds,callback):
        timer=self.loop.timer();self.callbacks.append(timer)
        def run():
            try:callback()
            finally:
                if timer in self.callbacks:self.callbacks.remove(timer)
        timer.start(seconds,run);return timer

    def cancel_timer(self,timer):
        if timer:
            timer.stop()
            if timer in self.callbacks:self.callbacks.remove(timer)

    def send(self,kind,**values):
        try:print(json.dumps({'type':kind,**values},ensure_ascii=False),flush=True)
        except (BrokenPipeError,OSError):self.quit()

    def read(self):
        try:
            for line in sys.stdin:
                try:data=json.loads(line)
                except ValueError:continue
                self.loop.post(lambda data=data:self.receive(data))
        finally:self.loop.post(self.quit)

    def receive(self,message):
        kind=message.get('type')
        if kind=='state':
            self.payload=message
            image=message.get('state',{}).get('product_picture')
            if image!=self.picture_key:
                self.picture_key=image;self.picture_data=''
                try:
                    path=Path(image)
                    neutral=self.root/'ui/assets/device-neutral.svg'
                    if (path.suffix.lower()=='.png' or path==neutral) and path.stat().st_size<=8*1024*1024:
                        mime='image/svg+xml' if path==neutral else 'image/png'
                        self.picture_data=f'data:{mime};base64,'+base64.b64encode(path.read_bytes()).decode('ascii')
                except (OSError,TypeError):pass
            self.payload={**message,'picture':self.picture_data}
            for window in list(self.windows.values()):
                window.publish()
                window.sync_motion_policy()
        elif kind=='show':self.show(message.get('view','main'))
        elif kind=='toggle_quick':
            if 'quick' in self.windows:self.windows['quick'].close()
            else:self.show('quick')
        elif kind=='quit':self.quit()
        elif kind=='test' and self.payload.get('fixture'):
            self.test_id=message.get('id');self.test_stage='pages';self.show('main')
            self.when_ready('main',lambda:self.windows['main'].browser.send(message))
        elif kind=='inspect' and os.environ.get('ENCOLITE_DIAGNOSTICS')=='1':
            self.show('main');self.when_ready('main',lambda:self.windows['main'].browser.send(message))

    def when_ready(self,kind,callback,attempts=100):
        window=self.windows.get(kind)
        if window and window.ready:callback()
        elif attempts:self.later(.1,lambda:self.when_ready(kind,callback,attempts-1))
        else:self.send('diagnostic',data={'result':'FAIL','error':'interface did not become ready'})

    def environment_ready(self):
        for window in list(self.windows.values()):window.create_browser()

    def fail(self,error):
        print(error,file=sys.stderr,flush=True)
        self.send('diagnostic',data={'result':'FAIL','error':str(error)});self.quit()

    def show(self,kind):
        if kind not in TITLES or self.stopping:return
        if kind in ('main','quick'):self.requested_view=kind
        if kind in self.windows:
            self.present_window(self.windows[kind]);return
        window=Window(self,kind);self.windows[kind]=window;self.handles[window.hwnd]=window
        if self.environment is None:
            loader=self.root/'WebView2Loader.dll'
            if not loader.exists():loader=self.root/'.tools/webview2/WebView2Loader.dll'
            profile=data_directory()/'WebView2'
            profile.mkdir(parents=True,exist_ok=True)
            self.environment=Environment(loader,profile,lambda:self.loop.post(self.environment_ready),self.fail)
        elif self.environment.pointer:window.create_browser()
        self.later(15,lambda:self.fail('图形界面启动超时') if not window.ready and not window.closed else None)
        self.send('view',view=kind,visible=True)

    def present_window(self,window):
        if not window.ready or window.closed:return
        if window.kind in ('main','quick') and self.requested_view!=window.kind:
            window.close(exiting=False,animate=False);return
        window.activate()
        if window.kind in ('main','quick'):
            # Keep the previous window until the destination has actually rendered.
            for old in list(self.windows.values()):
                if old is not window:old.close(exiting=False,reason='switch')
        self.send('view',view=window.kind,visible=True)

    def window_message(self,window,message):
        kind=message.get('type')
        if kind=='document_ready':
            window.publish();window.browser.send({'type':'init','view':window.kind,'page':window.page})
        elif kind=='ready':
            window.ready=True;self.present_window(window)
            if self.test_stage=='quick' and window.kind=='quick':
                window.browser.send({'type':'click_noise','mode':'transparency'})
                self.later(.3,lambda:window.capture('quick',0))
                self.later(5.6,self.finish_test)
        elif kind=='action':self.send('action',name=message.get('name'),args=message.get('args',[]))
        elif kind=='window':
            name=message.get('name')
            if name=='close':window.close()
            elif name=='minimize':s.ShowWindow(window.hwnd,6)
            elif name=='maximize' and window.kind=='main':s.ShowWindow(window.hwnd,9 if s.IsZoomed(window.hwnd) else 3)
            elif name=='page':
                page=message.get('page')
                if type(page) is int and 0<=page<=6:window.page=page
            elif name=='drag':
                s.api(s.user,'ReleaseCapture',W.BOOL)()
                s.api(s.user,'SendMessageW',s.LRESULT,W.HWND,W.UINT,W.WPARAM,W.LPARAM)(window.hwnd,0xA1,2,0)
            elif name=='hover' and window.kind=='notice':window.notice_timeout(message.get('inside',False))
            elif name=='motion' and type(message.get('enabled')) is bool:
                window.web_motion=message['enabled'];window.sync_motion_policy()
            elif name=='dismissed' and window.closing and message.get('token')==window.close_serial:
                if window.native_phase!='close':window.finish_close()
        elif kind=='capture' and (self.payload.get('fixture') or os.environ.get('ENCOLITE_DIAGNOSTICS')=='1'):
            name=message.get('name','');identifier=message.get('id')
            if name in {f'page-{n}' for n in range(7)}|{'quick','notice','main'}:window.capture(name,identifier)
        elif kind=='diagnostic' and (self.payload.get('fixture') or os.environ.get('ENCOLITE_DIAGNOSTICS')=='1'):
            data=message.get('data',{});data.update(self.geometry_diagnostic(window));self.send('diagnostic',data=data)
        elif kind=='test_step' and self.payload.get('fixture') and message.get('name')=='quick':
            self.test_stage='quick';self.show('quick')

    def geometry_diagnostic(self,window):
        outer=W.RECT();client=W.RECT();s.GetWindowRect(window.hwnd,C.byref(outer));s.GetClientRect(window.hwnd,C.byref(client))
        return {'caption_absent':not bool(s.GetWindowLong(window.hwnd,-16)&0x00C00000),
            'full_client':outer.right-outer.left==client.right and outer.bottom-outer.top==client.bottom,
            'foreground':s.GetForegroundWindow()==window.hwnd}

    def finish_test(self):
        if self.stopping:return
        try:
            assert 'quick' in self.windows,'manual quick control closed itself'
            self.test_stage='restoring';self.show('main')
            def finish():
                window=self.windows['main'];s.ShowWindow(window.hwnd,6);window.activate()
                assert not s.IsIconic(window.hwnd),'restore failed'
                def report():
                    self.send('diagnostic',data={'id':self.test_id,'result':'PASS','pages':7,'quick_persisted':True,**self.geometry_diagnostic(window)})
                    self.later(.6,window.close)
                self.later(.2,report)
            self.when_ready('main',finish)
        except Exception as error:self.send('diagnostic',data={'id':self.test_id,'result':'FAIL','error':str(error)})

    def closed(self,window,exiting):
        if self.windows.get(window.kind) is window:self.windows.pop(window.kind,None)
        self.handles.pop(window.hwnd,None)
        self.retired.append(window)  # Keep COM callbacks alive through final controller release.
        if not self.windows and exiting:
            self.send('closing');self.quit()
        elif self.windows:
            active=self.windows.get(self.requested_view) or next(iter(self.windows.values()))
            self.send('view',view=active.kind,visible=active.ready)

    def wndproc(self,hwnd,msg,wp,lp):
        try:
            if msg==0x8003 or msg==0x113 and wp==2:self.loop.drain();return 0
            if msg==0x83 or msg==0x85:return 0  # Full client area; no classic frame.
            if msg==0x86:return s.DefWindowProc(hwnd,msg,wp,-1)
            window=self.handles.get(hwnd)
            if window:return window.wndproc(msg,wp,lp)
        except Exception:traceback.print_exc()
        return s.DefWindowProc(hwnd,msg,wp,lp)

    def quit(self):
        if self.stopping:return
        self.stopping=True
        for window in list(self.windows.values()):window.close(exiting=False,animate=False)
        self.loop.quit()

    def run(self):
        threading.Thread(target=self.read,name='EncoLite-state',daemon=True).start()
        try:self.loop.run()
        finally:
            self.quit()
            if self.environment:self.environment.close()
            s.DestroyWindow(self.owner)


class Window:
    def __init__(self,app,kind):
        self.app=app;self.kind=kind;self.page=0;self.browser=None;self.ready=False;self.closed=False
        self.notice_timer=None;self.size=None;self.saved_maximized=False
        self.closing=False;self.close_serial=0;self.close_timer=None;self.close_exiting=True
        self.close_reason=None;self.presented=False;self.web_motion=True
        self.native_timer=None;self.native_phase=None;self.native_alpha=255;self.layered=False
        dpi=s.api(s.user,'GetDpiForSystem',W.UINT)()/96
        width,height=(864,640) if kind=='main' else (352,374) if kind=='quick' else (360,192)
        width=round(width*dpi);height=round(height*dpi)
        prefs=app.payload.get('preferences',{})
        saved=prefs.get('web_'+kind) or prefs.get(kind+'_window') or {}
        bounds,self.page=window_state(saved)
        if bounds is None:
            old,old_page=window_state(prefs.get('avalonia_'+kind,{}))
            if old:
                x,y,w,h,maximized=old;bounds=(x,y,round(w*dpi),round(h*dpi),maximized);self.page=old_page
        if bounds:
            x,y,w,h,self.saved_maximized=bounds
            if kind=='main':width=max(round(740*dpi),w);height=max(round(560*dpi),h)
        else:
            x=round((s.api(s.user,'GetSystemMetrics',C.c_int,C.c_int)(0)-width)/2)
            y=round((s.api(s.user,'GetSystemMetrics',C.c_int,C.c_int)(1)-height)/2)
            if kind!='main':
                point=W.POINT();s.GetCursorPos(C.byref(point));monitor=self.monitor(s.MonitorFromPoint(point,2))
                if monitor:x=monitor.work.right-width-round(14*dpi);y=monitor.work.bottom-height-round(14*dpi)
        monitor=self.monitor(s.MonitorFromPoint(W.POINT(x,y),2))
        if monitor:x,y,width,height,_=fit_bounds((x,y,width,height,False),(monitor.work.left,monitor.work.top,monitor.work.right,monitor.work.bottom))
        style=0x800F0000 if kind=='main' else 0x80000000
        extended=0x40000 if kind=='main' else 0x80|(0x08000000 if kind=='notice' else 0)
        self.hwnd=s.CreateWindow(extended,app.kind.name,TITLES[kind],style,x,y,width,height,None,None,app.kind.instance,None)
        if not self.hwnd:raise C.WinError(C.get_last_error())
        self.icon=s.LoadImage(None,str(app.root/'ui/assets/app-icon.ico'),1,0,0,0x10|0x40)
        if self.icon:
            fn=s.api(s.user,'SendMessageW',s.LRESULT,W.HWND,W.UINT,W.WPARAM,W.LPARAM)
            fn(self.hwnd,0x80,0,self.icon);fn(self.hwnd,0x80,1,self.icon)

    @staticmethod
    def monitor(handle):
        monitor=s.MonitorInfo(size=C.sizeof(s.MonitorInfo))
        return monitor if s.GetMonitorInfo(handle,C.byref(monitor)) else None

    def create_browser(self):
        if self.browser or self.closed:return
        self.browser=Browser(self.app.environment,self.hwnd,self.app.html,
            lambda message:self.app.window_message(self,message),lambda:None)

    def publish(self):
        if self.browser and not self.closed:self.browser.send(self.app.payload)

    @property
    def motion_enabled(self):
        state=self.app.payload.get('state',{})
        return not state.get('fast_mode',False) and state.get('system_motion') is not False and self.web_motion

    def cancel_close(self):
        if not self.closing:return False
        self.closing=False;self.close_serial+=1;self.app.cancel_timer(self.close_timer);self.close_timer=None
        self.stop_native_motion()
        return True

    def set_native_alpha(self,value):
        if self.closed:return False
        if not self.layered:
            s.SetWindowLong(self.hwnd,-20,s.GetWindowLong(self.hwnd,-20)|0x80000)
            self.layered=True
        setter=s.api(s.user,'SetLayeredWindowAttributes',W.BOOL,W.HWND,W.DWORD,C.c_ubyte,W.DWORD)
        if not setter(self.hwnd,0,max(0,min(255,round(value))),2):
            self.restore_native_surface();return False
        self.native_alpha=max(0,min(255,round(value)));return True

    def restore_native_surface(self):
        if self.closed:return
        if self.layered:
            setter=s.api(s.user,'SetLayeredWindowAttributes',W.BOOL,W.HWND,W.DWORD,C.c_ubyte,W.DWORD)
            setter(self.hwnd,0,255,2)
            s.SetWindowLong(self.hwnd,-20,s.GetWindowLong(self.hwnd,-20)&~0x80000)
            self.layered=False
        self.native_alpha=255

    def stop_native_motion(self,restore=False):
        if self.native_timer:self.native_timer.stop()
        self.native_phase=None
        if restore:self.restore_native_surface()

    def animate_native(self,target,duration,phase):
        self.stop_native_motion()
        if not self.set_native_alpha(self.native_alpha):return False
        started=time.monotonic();initial=self.native_alpha;self.native_phase=phase
        if self.native_timer is None:self.native_timer=self.app.loop.timer()
        def frame():
            if self.closed:return
            progress=min(1,(time.monotonic()-started)/duration)
            eased=1-(1-progress)**3 if phase=='open' else progress*progress
            if not self.set_native_alpha(initial+(target-initial)*eased):
                self.stop_native_motion()
                if phase=='close':self.finish_close()
                return
            if progress>=1:
                self.stop_native_motion()
                if phase=='close':self.finish_close()
                else:self.restore_native_surface()
        self.native_timer.start(.016,frame,repeat=True)
        return True

    def sync_motion_policy(self):
        if self.closed or self.motion_enabled:return
        if self.closing:self.finish_close()
        else:self.stop_native_motion(restore=True)

    def activate(self):
        if not self.ready or self.closed:return
        minimized=bool(s.IsIconic(self.hwnd))
        animate=not self.presented or self.closing or minimized
        self.cancel_close()
        native=bool(animate and self.motion_enabled)
        if native and (not self.presented or minimized):native=self.set_native_alpha(0)
        elif not native:self.stop_native_motion(restore=True)
        s.style_window(TITLES[self.kind],tool=self.kind!='main',hidden=False,passive=self.kind=='notice')
        if self.kind=='notice':
            s.SetWindowPos(self.hwnd,C.c_void_p(-1),0,0,0,0,0x53);self.notice_timeout(False,5)
        else:
            s.ShowWindow(self.hwnd,3 if self.saved_maximized else 9 if s.IsIconic(self.hwnd) else 5)
            self.saved_maximized=False;s.activate_window(self.hwnd)
            if self.browser and self.browser.controller:call(self.browser.controller,12,0,types=(C.c_int,))
        s.style_window(TITLES[self.kind],tool=self.kind!='main',passive=self.kind=='notice')
        self.presented=True
        self.browser.send({'type':'present','animate':bool(animate and self.motion_enabled),'native':native})
        if native:self.animate_native(255,.26 if self.kind=='main' else .23,'open')

    def notice_timeout(self,inside,seconds=3):
        self.app.cancel_timer(self.notice_timer);self.notice_timer=None
        if inside and self.closing and self.close_reason=='timeout':
            self.cancel_close();self.browser.send({'type':'present','animate':False})
            if self.motion_enabled:self.animate_native(255,.13,'open')
            else:self.stop_native_motion(restore=True)
        if not inside:self.notice_timer=self.app.later(seconds,lambda:self.close(reason='timeout'))

    def capture(self,name,identifier):
        folder=os.environ.get('ENCOLITE_CAPTURE_DIR')
        def done():
            if not self.closed:self.browser.send({'type':'captured','id':identifier})
        if folder and self.browser and self.ready:
            path=Path(folder)/(name+'.png');path.parent.mkdir(parents=True,exist_ok=True)
            self.browser.capture(path,done)
        else:done()

    def close(self,exiting=True,*,animate=True,reason='close'):
        if self.closed:return
        if self.closing and animate:return
        self.close_exiting=exiting;self.close_reason=reason
        if animate and self.ready and self.motion_enabled and not self.app.stopping:
            self.closing=True;self.close_serial+=1
            self.app.cancel_timer(self.notice_timer);self.notice_timer=None
            native=self.animate_native(0,.17,'close')
            self.browser.send({'type':'dismiss','token':self.close_serial,'native':native})
            # The browser never holds window cleanup hostage if rendering stalls.
            self.close_timer=self.app.later(.24,self.finish_close)
            return
        self.finish_close()

    def finish_close(self):
        if self.closed:return
        self.stop_native_motion()
        self.app.cancel_timer(self.close_timer);self.close_timer=None
        if self.kind!='notice':
            bounds=s.window_placement(TITLES[self.kind])
            if bounds:self.app.send('action',name='save_window',args=[self.kind,list(bounds),self.page])
        self.closed=True
        self.app.cancel_timer(self.notice_timer);self.notice_timer=None
        if self.browser:self.browser.close()
        s.DestroyWindow(self.hwnd)
        if self.icon:s.DestroyIcon(self.icon)
        self.app.closed(self,self.close_exiting)

    def wndproc(self,msg,wp,lp):
        if msg==0x10:self.close();return 0
        if msg==5:
            if not s.IsIconic(self.hwnd):
                rect=W.RECT();s.GetClientRect(self.hwnd,C.byref(rect));size=(rect.right,rect.bottom,bool(s.IsZoomed(self.hwnd)))
                if size!=self.size:
                    self.size=size
                    if self.browser:self.browser.resize()
                    s.round_window(TITLES[self.kind])
            return 0
        if msg==3 and self.browser and self.browser.controller:call(self.browser.controller,23)
        if msg==0x24:
            info=C.cast(lp,C.POINTER(MinMaxInfo)).contents;scale=(s.GetDpiForWindow(self.hwnd) or 96)/96
            info.min_track=W.POINT(round(740*scale),round(560*scale))
            monitor=self.monitor(s.MonitorFromWindow(self.hwnd,2))
            if monitor:
                r,m=monitor.work,monitor.monitor
                info.max_position=W.POINT(r.left-m.left,r.top-m.top);info.max_size=W.POINT(r.right-r.left,r.bottom-r.top)
            return 0
        if msg==0x84:
            if self.kind!='main' or s.IsZoomed(self.hwnd):return 1
            rect=W.RECT();s.GetWindowRect(self.hwnd,C.byref(rect));x=C.c_short(lp&0xffff).value;y=C.c_short((lp>>16)&0xffff).value
            edge=round(6*(s.GetDpiForWindow(self.hwnd) or 96)/96)
            left=x<rect.left+edge;right=x>=rect.right-edge;top=y<rect.top+edge;bottom=y>=rect.bottom-edge
            if top:return 13 if left else 14 if right else 12
            if bottom:return 16 if left else 17 if right else 15
            return 10 if left else 11 if right else 1
        if msg==0x2E0:
            rect=C.cast(lp,C.POINTER(W.RECT)).contents
            s.SetWindowPos(self.hwnd,None,rect.left,rect.top,rect.right-rect.left,rect.bottom-rect.top,0x14);return 0
        return s.DefWindowProc(self.hwnd,msg,wp,lp)
