"""Modern ttk windows, fed exclusively by the backend's JSON projection."""
from pathlib import Path
import ctypes as C
from ctypes import wintypes as W
import json, os, queue, sys, threading, time
import tkinter as tk
from tkinter import ttk, messagebox, font
import sv_ttk
from . import windows_shell as shell
from .preferences import window_state, fit_bounds

PAGES=[(0,'我的耳机'),(1,'声音与音效'),(4,'耳机功能'),(5,'自定义音效'),(6,'连接的设备'),(2,'应用设置'),(3,'关于 Enco Lite')]


class Desktop:
    def __init__(self,root):
        self.path=root;self.state={};self.preferences={};self.windows={};self.fixture=False
        self.incoming=queue.Queue();self.photos={};self.closing=False;self.theme=None
        sys.stdin.reconfigure(encoding='utf-8');sys.stdout.reconfigure(encoding='utf-8')
        self.root=tk.Tk();self.root.withdraw()
        font.nametofont('TkDefaultFont').configure(family='Microsoft YaHei UI',size=10)
        font.nametofont('TkTextFont').configure(family='Microsoft YaHei UI',size=10)
        self.scale=self.root.winfo_fpixels('1i')/96
        self.style=ttk.Style(self.root);self.apply_theme(False)
        threading.Thread(target=self.read,name='EncoLite-state',daemon=True).start()

    def apply_theme(self,dark):
        if self.theme==dark:return
        self.theme=dark;sv_ttk.set_theme('dark' if dark else 'light',self.root)
        self.bg='#202020' if dark else '#f5f6f8';self.card='#292929' if dark else '#ffffff'
        self.fg='#f3f3f3' if dark else '#202827';self.muted='#b4bbb9' if dark else '#687571'
        self.style.configure('.',font=('Microsoft YaHei UI',10))
        for name,bg in [('TFrame',self.bg),('TLabel',self.bg),('Card.TFrame',self.card),('Card.TLabel',self.card)]:
            self.style.configure(name,background=bg,foreground=self.fg)
        self.style.configure('Muted.TLabel',foreground=self.muted)
        self.style.configure('Title.TLabel',font=('Microsoft YaHei UI',17,'bold'))
        self.style.configure('Name.TLabel',font=('Microsoft YaHei UI',14,'bold'))
        self.style.configure('Battery.TLabel',font=('Microsoft YaHei UI',17,'bold'),background=self.card)
        self.style.configure('Nav.TButton',anchor='w',padding=(12,10))
        self.style.configure('Selected.TButton',foreground='#16876b')
        self.style.configure('Noise.TButton',padding=(8,13))

    def send(self,kind,**values):
        try:print(json.dumps({'type':kind,**values},ensure_ascii=False),flush=True)
        except (BrokenPipeError,OSError):self.stop()

    def action(self,name,*args):self.send('action',name=name,args=list(args))

    def read(self):
        try:
            for line in sys.stdin:
                try:self.incoming.put(json.loads(line))
                except ValueError:pass
        finally:self.incoming.put({'type':'quit'})

    def pump(self):
        try:
            while True:
                message=self.incoming.get_nowait();kind=message.get('type')
                if kind=='state':
                    self.state=message['state'];self.preferences=message['preferences'];self.fixture=message.get('fixture',False)
                    self.apply_theme(bool(self.state.get('dark')))
                    for window in list(self.windows.values()):window.refresh()
                elif kind=='show':self.show(message.get('view','main'))
                elif kind=='toggle_quick':
                    if 'quick' in self.windows:self.windows['quick'].close()
                    else:self.show('quick')
                elif kind=='quit':self.stop();return
                elif kind=='test' and self.fixture:self.test(message.get('id'))
                elif kind=='inspect' and os.environ.get('ENCOLITE_DIAGNOSTICS')=='1':self.inspect(message.get('id'))
        except queue.Empty:pass
        if not self.closing:self.root.after(40,self.pump)

    def show(self,kind):
        if kind not in ('main','quick','notice'):return
        previous=self.windows.get(kind)
        if previous:
            previous.activate();return
        window=Window(self,kind);self.windows[kind]=window
        # Construct the target before destroying the old view, keeping the UI process alive.
        if kind in ('main','quick'):
            for other in list(self.windows.values()):
                if other is not window:other.close(exiting=False)
        window.activate()
        self.send('view',view=kind,visible=True)

    def closed(self,window,exiting):
        self.windows.pop(window.kind,None)
        if not self.windows and exiting:
            self.send('closing');self.stop()
        elif self.windows:
            kind='main' if 'main' in self.windows else next(iter(self.windows))
            self.send('view',view=kind,visible=True)

    def stop(self):
        if self.closing:return
        self.closing=True
        for window in list(self.windows.values()):window.close(exiting=False)
        self.root.destroy()

    def picture(self,path,size):
        path=str(path or '');size=round(size*self.scale);key=(path,size)
        if key in self.photos:return self.photos[key]
        try:
            source=Path(path)
            # Build-time thumbnails use GDI+; no image decoder extension is shipped.
            thumbnail=self.path/'ui/assets/thumbs'/f'{source.stem}-{size}.png'
            photo=tk.PhotoImage(master=self.root,file=str(thumbnail if thumbnail.exists() else source))
            if max(photo.width(),photo.height())>size:
                factor=max(1,(max(photo.width(),photo.height())+size-1)//size)
                photo=photo.subsample(factor,factor)
            self.photos[key]=photo;return photo
        except (tk.TclError,OSError):return None

    def inspect(self,identifier,report=True):
        self.show('main');window=self.windows['main']
        for page,_ in PAGES:
            window.select(page);self.root.update_idletasks();self.capture(window,f'page-{page}')
        if report:self.send('diagnostic',data={'id':identifier,'result':'PASS','pages':len(PAGES),
            'model':self.state.get('model_name'),'picture':self.state.get('product_picture'),
            'caption_absent':not bool(shell.GetWindowLong(window.hwnd,-16)&0x00C00000)})

    def capture(self,window,name):
        folder=os.environ.get('ENCOLITE_CAPTURE_DIR')
        if folder:
            from .window_capture import capture
            capture(window.hwnd,Path(folder)/(name+'.bmp'))

    def test(self,identifier):
        try:
            self.inspect(identifier,report=False)
            self.show('main');window=self.windows['main'];window.select(0)
            window.noise_buttons['off'].invoke()
            self.show('quick');self.windows['quick'].noise_buttons['transparency'].invoke()
            self.root.update_idletasks();self.capture(self.windows['quick'],'quick')
            def finish():
                try:
                    assert 'quick' in self.windows,'manual quick control closed itself'
                    self.show('main');win=self.windows['main'];shell.ShowWindow(win.hwnd,6);win.activate()
                    assert not shell.IsIconic(win.hwnd)
                    outer=W.RECT();client=W.RECT()
                    shell.GetWindowRect(win.hwnd,C.byref(outer));shell.GetClientRect(win.hwnd,C.byref(client))
                    self.send('diagnostic',data={'id':identifier,'result':'PASS','pages':7,
                        'caption_absent':not bool(shell.GetWindowLong(win.hwnd,-16)&0x00C00000),
                        'full_client':outer.right-outer.left==client.right and outer.bottom-outer.top==client.bottom,
                        'quick_persisted':True,'foreground':shell.GetForegroundWindow()==win.hwnd})
                    self.root.after(600,win.close)
                except Exception as e:self.send('diagnostic',data={'id':identifier,'result':'FAIL','error':str(e)})
            self.root.after(5600,finish)
        except Exception as e:self.send('diagnostic',data={'id':identifier,'result':'FAIL','error':str(e)})

    def run(self):self.root.after(0,self.pump);self.root.mainloop()


class Window:
    def __init__(self,app,kind):
        self.app=app;self.kind=kind;self.bindings=[];self.updating=False;self.signature=None;self.page=0
        self.noise_buttons={};self.notice_timer=None;self.maximized=False;self.normal_bounds=None
        self.top=tk.Toplevel(app.root);self.top.withdraw();self.top.overrideredirect(True)
        self.title={'main':'Enco Lite · OPPO 耳机助手','quick':'Enco Lite · 快捷控制','notice':'Enco Lite · 连接提示'}[kind]
        self.top.title(self.title);self.top.configure(bg=app.bg)
        self.top.protocol('WM_DELETE_WINDOW',self.close)
        try:self.top.iconbitmap(str(app.path/'ui/assets/app-icon.ico'))
        except tk.TclError:pass
        self.outer=ttk.Frame(self.top,padding=1);self.outer.pack(fill='both',expand=True)
        self.header=ttk.Frame(self.outer,padding=(12,3,4,3));self.header.pack(fill='x')
        self.caption=ttk.Label(self.header,text='Enco Lite' if kind=='main' else '耳机已连接' if kind=='notice' else '',font=('Microsoft YaHei UI',11,'bold'))
        self.caption.pack(side='left',fill='x',expand=True)
        for control in (self.header,self.caption):
            control.bind('<ButtonPress-1>',self.drag_start);control.bind('<B1-Motion>',self.drag)
            if kind=='main':control.bind('<Double-Button-1>',lambda e:self.maximize())
        if kind=='main':
            ttk.Button(self.header,text='—',width=3,command=self.minimize).pack(side='left')
            ttk.Button(self.header,text='□',width=3,command=self.maximize).pack(side='left',padx=2)
        ttk.Button(self.header,text='×',width=3,command=self.close).pack(side='right')
        self.body=ttk.Frame(self.outer);self.body.pack(fill='both',expand=True)
        if kind=='main':self.build_shell()
        else:
            self.content=ttk.Frame(self.body,padding=(14,5,14,14));self.content.pack(fill='both',expand=True)
        self.restore();self.refresh();self.top.update_idletasks()
        self.hwnd=shell.api(shell.user,'GetAncestor',W.HWND,W.HWND,W.UINT)(self.top.winfo_id(),2)
        extended=shell.GetWindowLong(self.hwnd,-20)
        shell.SetWindowLong(self.hwnd,-20,(extended|0x40000)&~0x80 if kind=='main' else (extended|0x80)&~0x40000)
        if kind=='notice':shell.SetWindowLong(self.hwnd,-20,shell.GetWindowLong(self.hwnd,-20)|0x08000000)
        shell.SetWindowPos(self.hwnd,None,0,0,0,0,0x37)
        self.top.bind('<Configure>',self.configured)
        if kind=='notice':
            self.top.bind('<Enter>',self.pause_notice);self.top.bind('<Leave>',self.resume_notice)
        self.top.bind('<Escape>',lambda e:self.close())
        if kind=='main':
            grip=ttk.Sizegrip(self.outer);grip.place(relx=1,rely=1,anchor='se')

    def px(self,value):return round(value*self.app.scale)

    def restore(self):
        default={'main':(832,620),'quick':(352,376),'notice':(360,192)}[self.kind]
        width,height=map(self.px,default)
        saved=self.app.preferences.get('tk_'+self.kind) or self.app.preferences.get(self.kind+'_window') or {}
        bounds,page=window_state(saved);self.page=page
        if bounds:
            x,y,w,h,self.maximized=bounds
            if self.kind=='main':width=max(self.px(740),w);height=max(self.px(560),h)
        else:
            x=max(0,(self.top.winfo_screenwidth()-width)//2);y=max(0,(self.top.winfo_screenheight()-height)//2)
            if self.kind!='main':x=max(0,self.top.winfo_screenwidth()-width-self.px(20));y=max(0,self.top.winfo_screenheight()-height-self.px(64))
        monitor=shell.MonitorInfo(size=C.sizeof(shell.MonitorInfo))
        if shell.GetMonitorInfo(shell.MonitorFromPoint(W.POINT(x,y),2),C.byref(monitor)):
            x,y,width,height,_=fit_bounds((x,y,width,height,False),(monitor.work.left,monitor.work.top,monitor.work.right,monitor.work.bottom))
        self.top.geometry(f'{width}x{height}{x:+d}{y:+d}')
        if self.kind=='main':self.top.minsize(self.px(740),self.px(560))

    def configured(self,event):
        if event.widget is self.top and hasattr(self,'hwnd'):
            size=(event.width,event.height,self.maximized)
            if getattr(self,'rounded_size',None)!=size:
                # SetWindowRgn can itself raise Configure; never repeat for that event.
                self.rounded_size=size
                shell.round_window(self.title,maximized=self.maximized)

    def activate(self):
        self.top.deiconify();self.top.update_idletasks()
        shell.style_window(self.title,tool=self.kind!='main',passive=self.kind=='notice')
        if self.kind=='notice':
            shell.SetWindowPos(self.hwnd,C.c_void_p(-1),0,0,0,0,0x53)
            self.resume_notice(milliseconds=5000)
        else:
            shell.activate_window(self.hwnd);self.top.focus_force()
            if self.maximized and self.normal_bounds is None:self.maximized=False;self.maximize()

    def minimize(self):shell.ShowWindow(self.hwnd,6)

    def maximize(self):
        if self.maximized:
            if self.normal_bounds:self.top.geometry(self.normal_bounds)
            self.maximized=False
        else:
            self.normal_bounds=self.top.geometry();m=shell.MonitorInfo(size=C.sizeof(shell.MonitorInfo))
            if shell.GetMonitorInfo(shell.MonitorFromWindow(self.hwnd,2),C.byref(m)):
                r=m.work;self.top.geometry(f'{r.right-r.left}x{r.bottom-r.top}{r.left:+d}{r.top:+d}');self.maximized=True
        self.top.update_idletasks();shell.round_window(self.title,maximized=self.maximized)

    def drag_start(self,event):self.drag_origin=(event.x_root,event.y_root,self.top.winfo_x(),self.top.winfo_y())
    def drag(self,event):
        if self.maximized:return
        x,y,wx,wy=self.drag_origin;self.top.geometry(f'{wx+event.x_root-x:+d}{wy+event.y_root-y:+d}')

    def pause_notice(self,event=None):
        if self.notice_timer:self.top.after_cancel(self.notice_timer);self.notice_timer=None
    def resume_notice(self,event=None,milliseconds=3000):
        if self.kind!='notice':return
        if event:
            x,y=self.top.winfo_pointerxy()
            if self.top.winfo_containing(x,y) is not None and str(self.top.winfo_containing(x,y)).startswith(str(self.top)):return
        self.pause_notice();self.notice_timer=self.top.after(milliseconds,self.close)

    def close(self,exiting=True):
        if not self.top.winfo_exists():return
        self.pause_notice()
        if self.kind!='notice':
            bounds=shell.window_placement(self.title)
            if bounds:
                bounds=list(bounds);bounds[4]=self.maximized
                if self.maximized and self.normal_bounds:
                    import re
                    match=re.fullmatch(r'(\d+)x(\d+)([+-]\d+)([+-]\d+)',self.normal_bounds)
                    if match:w,h,x,y=map(int,match.groups());bounds=[x,y,w,h,True]
                self.app.action('save_window',self.kind,bounds,self.page)
        self.top.destroy();self.app.closed(self,exiting)

    def build_shell(self):
        self.side=ttk.Frame(self.body,padding=(12,18));self.side.pack(side='left',fill='y')
        ttk.Label(self.side,text='Enco Lite',font=('Microsoft YaHei UI',17,'bold')).pack(anchor='w',pady=(0,22))
        self.nav={}
        for number,title in PAGES:
            button=ttk.Button(self.side,text=title,style='Nav.TButton',width=14,command=lambda n=number:self.select(n))
            button.pack(fill='x',pady=3);self.nav[number]=button
        ttk.Button(self.side,text='快捷控制',command=lambda:self.app.action('show','quick')).pack(side='bottom',fill='x',pady=10)
        ttk.Separator(self.body,orient='vertical').pack(side='left',fill='y')
        right=ttk.Frame(self.body,padding=(20,14,18,12));right.pack(fill='both',expand=True)
        self.heading=ttk.Label(right,style='Title.TLabel');self.heading.pack(anchor='w',pady=(0,14))
        self.status=ttk.Label(right,style='Muted.TLabel',wraplength=self.px(540));self.status.pack(side='bottom',anchor='w',fill='x',pady=(10,0))
        viewport=ttk.Frame(right);viewport.pack(fill='both',expand=True)
        self.canvas=tk.Canvas(viewport,highlightthickness=0,bd=0,bg=self.app.bg)
        self.scrollbar=ttk.Scrollbar(viewport,orient='vertical',command=self.canvas.yview)
        self.scrollbar.pack(side='right',fill='y');self.canvas.pack(side='left',fill='both',expand=True)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.content=ttk.Frame(self.canvas);self.content_id=self.canvas.create_window((0,0),window=self.content,anchor='nw')
        self.content.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>',lambda e:self.canvas.itemconfigure(self.content_id,width=e.width))
        self.top.bind('<MouseWheel>',self.wheel,add='+')

    def wheel(self,event):
        # Let combo boxes and scales retain their native wheel behavior.
        if not isinstance(event.widget,(ttk.Combobox,ttk.Scale)) and self.canvas.bbox('all') and self.content.winfo_height()>self.canvas.winfo_height():
            self.canvas.yview_scroll(-int(event.delta/120),'units')

    def select(self,page):
        self.page=page;self.signature=None;self.refresh()
        if self.kind=='main':self.canvas.yview_moveto(0)

    def label(self,parent,text='',style=None,**options):
        widget=ttk.Label(parent,text=text,style=style or 'TLabel',**options);return widget
    def bound(self,parent,key,style=None,**options):
        label=self.label(parent,style=style,**options);self.bindings.append(lambda:label.configure(text=self.s.get(key) or ''));return label
    def button(self,parent,text,action,*args,enabled=None,**options):
        button=ttk.Button(parent,text=text,command=lambda:self.app.action(action,*args),**options)
        self.bindings.append(lambda:button.configure(state='normal' if (enabled() if enabled else not self.s.get('busy')) else 'disabled'))
        return button
    def card_frame(self,parent):
        frame=ttk.Frame(parent,style='Card.TFrame',padding=14);frame.pack(fill='x',pady=(0,10));return frame
    def row(self,parent,title,detail=''):
        frame=self.card_frame(parent);labels=ttk.Frame(frame,style='Card.TFrame');labels.pack(side='left',fill='x',expand=True)
        self.label(labels,title,style='Card.TLabel').pack(anchor='w')
        if detail:self.label(labels,detail,style='Card.TLabel',foreground=self.app.muted,wraplength=self.px(270)).pack(anchor='w',pady=(4,0))
        return frame
    def combo(self,parent,items,selected,callback,enabled=None,width=19):
        combo=ttk.Combobox(parent,state='readonly',width=width);values=[]
        def update():
            nonlocal values
            values=list(items());combo.configure(values=[str(name) for _,name in values])
            index=next((i for i,(key,_) in enumerate(values) if key==selected()),-1)
            if index>=0:combo.current(index)
            else:combo.set('')
            combo.configure(state='readonly' if values and (enabled() if enabled else not self.s.get('busy')) else 'disabled')
        def changed(event):
            if not self.updating and 0<=combo.current()<len(values):callback(values[combo.current()][0])
        combo.bind('<<ComboboxSelected>>',changed);self.bindings.append(update);return combo
    def toggle(self,parent,title,detail,key,action):
        row=self.row(parent,title,detail);value=tk.BooleanVar(self.top)
        def changed():
            if not self.updating:self.app.action(action,value.get())
        widget=ttk.Checkbutton(row,variable=value,style='Switch.TCheckbutton',command=changed);widget.pack(side='right',padx=(12,0))
        self.bindings.append(lambda:value.set(bool(self.s.get(key))));return widget
    def noise(self,parent):
        row=ttk.Frame(parent);row.pack(fill='x',pady=(2,12));self.noise_buttons={}
        for i,(key,name) in enumerate([('anc','降噪'),('transparency','通透'),('off','关闭')]):
            row.columnconfigure(i,weight=1,uniform='noise')
            button=ttk.Button(row,text=name,style='Noise.TButton',command=lambda k=key:self.app.action('change_noise',self.s.get('anc_level') if k=='anc' else k))
            button.grid(row=0,column=i,sticky='ew',padx=(0,6 if i<2 else 0));self.noise_buttons[key]=button
            def update(button=button,key=key):
                mode=self.s.get('noise');selected=(mode not in (None,'','off','transparency','vocal')) if key=='anc' else mode in ('transparency','vocal') if key=='transparency' else mode=='off'
                button.configure(style='Accent.TButton' if selected else 'Noise.TButton',state='normal' if self.s.get('can_'+key) and not self.s.get('busy') else 'disabled')
            self.bindings.append(update)
    def sound(self,parent):
        for title,is_noise in [('降噪强度',True),('耳机音效',False)]:
            row=ttk.Frame(parent);row.pack(fill='x',pady=(0,10));self.label(row,title,style='Muted.TLabel').pack(side='left')
            items=(lambda:[(r['key'],r['name']) for r in self.s.get('noise_options') or [] if r['key'] not in ('off','transparency','vocal')]) if is_noise else lambda:[(r['id'],r['name']) for r in self.s.get('presets') or []]
            self.combo(row,items,lambda n=is_noise:self.s.get('anc_level' if n else 'preset'),
                lambda key,n=is_noise:self.app.action('change_noise' if n else 'change_preset',key),
                enabled=lambda n=is_noise:self.s.get('can_anc' if n else 'can_equalizer') and not self.s.get('busy')).pack(side='right')
    def batteries(self,parent):
        row=ttk.Frame(parent);row.pack(fill='x',pady=(0,12))
        for i,(key,title) in enumerate([('left','左耳'),('case','充电盒'),('right','右耳')]):
            row.columnconfigure(i,weight=1,uniform='battery')
            card=ttk.Frame(row,style='Card.TFrame',padding=(10,9));card.grid(row=0,column=i,sticky='ew',padx=(0,6 if i<2 else 0))
            self.label(card,title,style='Card.TLabel',foreground=self.app.muted).pack(anchor='w')
            line=ttk.Frame(card,style='Card.TFrame');line.pack(fill='x',pady=(4,0))
            self.bound(line,key+'_value',style='Battery.TLabel').pack(side='left')
            charging=self.label(line,'',style='Card.TLabel',font=('Segoe UI Symbol',11),foreground='#16876b');charging.pack(side='right',padx=(3,0))
            self.bindings.append(lambda key=key,label=charging:label.configure(text='⚡' if self.s.get(key+'_charging') else ''))
    def image(self,parent,size):
        label=self.label(parent,style='Card.TLabel')
        def update():
            photo=self.app.picture(self.s.get('product_picture'),size);label.configure(image=photo or '');label.image=photo
        self.bindings.append(update);return label

    @property
    def s(self):return self.app.state

    def refresh(self):
        self.updating=True
        try:
            # Rebuild only on capability/layout changes; live state preserves edit focus.
            signature=(self.kind,self.page,self.app.theme,
                tuple((r.get('key'),r.get('title')) for r in self.s.get('switches') or []),
                tuple(r.get('label') for r in self.s.get('bands') or []),
                json.dumps([self.s.get(k) for k in ('spatial_options','game_options','find_visible','multi_devices','multi_writable','custom_available')],sort_keys=True))
            if signature!=self.signature:
                self.signature=signature;self.bindings=[]
                for child in self.content.winfo_children():child.destroy()
                if self.kind=='main':
                    self.heading.configure(text=dict(PAGES)[self.page]);self.canvas.configure(bg=self.app.bg)
                    for n,button in self.nav.items():button.configure(style='Accent.TButton' if n==self.page else 'Nav.TButton')
                    {0:self.overview,1:self.sounds,2:self.settings,3:self.about,4:self.features,5:self.equalizer,6:self.devices}[self.page]()
                elif self.kind=='quick':self.quick()
                else:self.notice()
            for binding in list(self.bindings):binding()
            if self.kind=='main':self.status.configure(text=self.s.get('status') or '',foreground='#c24747' if self.s.get('status_error') else self.app.muted)
            elif self.kind=='quick':self.caption.configure(text=self.s.get('model_name') or '未连接耳机')
        finally:self.updating=False

    def overview(self):
        card=self.card_frame(self.content);self.image(card,112).pack(side='left',padx=(0,18))
        details=ttk.Frame(card,style='Card.TFrame');details.pack(side='left',fill='x',expand=True)
        self.bound(details,'model_name',style='Card.TLabel',font=('Microsoft YaHei UI',14,'bold')).pack(anchor='w')
        self.bound(details,'device_info',style='Card.TLabel',foreground=self.app.muted,wraplength=self.px(340)).pack(anchor='w',pady=(7,10))
        connect=self.button(details,'连接耳机','change_connection',enabled=lambda:not self.s.get('busy') or self.s.get('connecting') and not self.s.get('cancelling'),style='Accent.TButton');connect.pack(anchor='w')
        self.bindings.append(lambda:connect.configure(text='正在取消…' if self.s.get('cancelling') else '取消连接' if self.s.get('connecting') else '断开控制连接' if self.s.get('connected') else '连接耳机'))
        self.batteries(self.content);self.label(self.content,'聆听模式').pack(anchor='w',pady=(2,7));self.noise(self.content);self.sound(self.content)
    def sounds(self):self.noise(self.content);self.sound(self.content)
    def quick(self):
        self.batteries(self.content);self.noise(self.content);self.sound(self.content)
        self.bound(self.content,'status',style='Muted.TLabel',wraplength=self.px(320)).pack(fill='x',pady=(0,8))
        self.button(self.content,'打开主窗口','show','main',enabled=lambda:True).pack(fill='x')
    def notice(self):
        row=ttk.Frame(self.content);row.pack(fill='x',pady=(0,12));self.image(row,56).pack(side='left',padx=(0,12))
        labels=ttk.Frame(row);labels.pack(side='left',fill='x',expand=True)
        self.bound(labels,'model_name',style='Name.TLabel').pack(anchor='w')
        text=self.label(labels,style='Muted.TLabel');text.pack(anchor='w',pady=(5,0))
        self.bindings.append(lambda:text.configure(text=' · '.join(f'{title} {self.s.get(key+"_value")}' for key,title in [('left','左'),('right','右')] if self.s.get(key+'_value') not in (None,'','—'))))
        self.button(self.content,'打开快捷控制','show','quick',enabled=lambda:True).pack(fill='x')
    def features(self):
        row=self.row(self.content,'聆听模式')
        self.combo(row,lambda:[(r['key'],r['name']) for r in self.s.get('noise_options') or []],lambda:self.s.get('noise'),lambda key:self.app.action('change_noise',key)).pack(side='right')
        if self.s.get('spatial_visible'):
            row=self.row(self.content,'空间音频')
            self.combo(row,lambda:[(r['id'],r['name']) for r in self.s.get('spatial_options') or []],lambda:self.s.get('spatial_mode'),lambda key:self.app.action('change_spatial',key)).pack(side='right')
        for item in self.s.get('switches') or []:
            key=item['key'];row=self.row(self.content,item['title'],item['detail']);value=tk.BooleanVar(self.top)
            toggle=ttk.Checkbutton(row,variable=value,style='Switch.TCheckbutton',command=lambda key=key,v=value:self.app.action('change_feature',key,v.get()))
            toggle.pack(side='right',padx=(12,0))
            def update(key=key,v=value,w=toggle):
                item=next((r for r in self.s.get('switches') or [] if r['key']==key),{})
                v.set(bool(item.get('checked')));w.configure(state='normal' if item.get('enabled') and not self.s.get('busy') else 'disabled')
            self.bindings.append(update)
        if self.s.get('game_options'):
            row=self.row(self.content,'游戏音效')
            self.combo(row,lambda:[(r['id'],r['name']) for r in self.s.get('game_options') or []],lambda:self.s.get('game_type'),lambda key:self.app.action('change_game',key)).pack(side='right')
        if self.s.get('find_visible'):
            row=self.row(self.content,'查找耳机','取下耳机后播放提示音')
            button=ttk.Button(row,command=lambda:self.app.action('find_device',not self.s.get('finding')));button.pack(side='right')
            self.bindings.append(lambda:button.configure(text='停止提示音' if self.s.get('finding') else '播放提示音',state='disabled' if self.s.get('busy') else 'normal'))
    def equalizer(self):
        available=lambda:bool(self.s.get('custom_available') and not self.s.get('busy'))
        self.label(self.content,'将音色保存到耳机，随时继续聆听。' if self.s.get('custom_available') else '连接支持自定义均衡器的耳机后即可调整。',style='Muted.TLabel').pack(anchor='w',pady=(0,12))
        row=ttk.Frame(self.content);row.pack(fill='x',pady=(0,12))
        self.combo(row,lambda:list(enumerate(self.s.get('custom_names') or [])),lambda:self.s.get('custom_index'),lambda key:self.app.action('select_custom',key),enabled=available,width=16).pack(side='left')
        name=ttk.Entry(row,width=21);name.pack(side='right',fill='x',expand=True,padx=(12,0))
        def update_name():
            if self.top.focus_get() is not name:
                name.configure(state='normal');name.delete(0,'end');name.insert(0,self.s.get('eq_name') or '')
            name.configure(state='normal' if available() else 'disabled')
        self.bindings.append(update_name)
        name.bind('<FocusOut>',lambda e:self.app.action('edit_custom_name',name.get()) if not self.updating else None)
        for index,band in enumerate(self.s.get('bands') or []):
            row=ttk.Frame(self.content);row.pack(fill='x',pady=(0,9))
            self.label(row,band['label'],width=7,style='Muted.TLabel').pack(side='left')
            value=tk.DoubleVar(self.top);gain=self.label(row,width=6,anchor='e');gain.pack(side='right')
            def changed(raw,index=index):
                if not self.updating:self.app.action('edit_gain',index,round(float(raw)))
            scale=ttk.Scale(row,from_=self.s.get('eq_minimum',-6),to=self.s.get('eq_maximum',6),variable=value,command=changed)
            scale.pack(side='left',fill='x',expand=True,padx=8)
            def update(index=index,v=value,label=gain,widget=scale):
                current=(self.s.get('bands') or [])[index]['gain'];v.set(current);label.configure(text=f'{current:+} dB');widget.configure(state='normal' if available() else 'disabled')
            self.bindings.append(update)
        row=ttk.Frame(self.content);row.pack(fill='x',pady=(10,0))
        def write(action):
            if action=='delete' and not messagebox.askyesno('删除音效','删除当前自定义音效？',parent=self.top):return
            self.app.action('edit_custom_name',name.get());self.app.action('write_custom',action)
        for title,action in [('保存并使用','save'),('试听修改','preview'),('删除音效','delete')]:
            button=ttk.Button(row,text=title,command=lambda a=action:write(a));button.pack(side='left',padx=(0,7))
            self.bindings.append(lambda w=button,a=action:w.configure(state='normal' if available() and (a=='save' or (self.s.get('custom_index') or 0)>0) else 'disabled'))
        self.label(self.content,'试听会同步修改耳机中的当前条目。',style='Muted.TLabel').pack(anchor='w',pady=(12,0))
    def devices(self):
        self.label(self.content,self.s.get('priority_text') if self.s.get('multi_available') else '连接支持多设备管理的耳机后即可查看。',style='Muted.TLabel',wraplength=self.px(540)).pack(anchor='w',pady=(0,12))
        self.button(self.content,'刷新列表','refresh',enabled=lambda:self.s.get('multi_available') and not self.s.get('busy')).pack(anchor='w',pady=(0,12))
        for item in self.s.get('multi_devices') or []:
            card=self.card_frame(self.content);self.label(card,item['name'],style='Card.TLabel',font=('Microsoft YaHei UI',12,'bold')).pack(anchor='w')
            self.label(card,item['detail'],style='Card.TLabel',foreground=self.app.muted).pack(anchor='w',pady=(5,0))
            if self.s.get('multi_writable'):
                row=ttk.Frame(card,style='Card.TFrame');row.pack(fill='x',pady=(10,0));address=item['address']
                self.button(row,'断开' if item['connected'] else '连接','operate_multi','disconnect' if item['connected'] else 'connect',address).pack(side='left')
                self.button(row,'优先连接','operate_multi','priority',address,enabled=lambda c=item['connected']:c and not self.s.get('busy')).pack(side='left',padx=6)
                def unpair(address=address):
                    if messagebox.askyesno('取消配对','从耳机的设备列表中取消此配对？',parent=self.top):self.app.action('operate_multi','unpair',address)
                ttk.Button(row,text='取消配对',command=unpair).pack(side='left')
        if self.s.get('multi_writable'):self.button(self.content,'自动连接优先级','operate_multi','auto','').pack(anchor='w')
    def settings(self):
        self.toggle(self.content,'深色外观','','dark','change_theme')
        self.toggle(self.content,'连接提示','连接就绪时显示快捷提示','connection_popup','change_connection_popup')
        row=self.row(self.content,'已配对的耳机','先在 Windows 蓝牙设置中配对')
        self.button(row,'刷新','scan').pack(side='right',padx=(6,0))
        self.combo(row,lambda:list(enumerate(self.s.get('device_names') or [])),lambda:self.s.get('device_index'),lambda key:self.app.action('select_device',key),width=17).pack(side='right')
        row=self.row(self.content,'耳机型号','自动识别不正确时可手动选择')
        self.combo(row,lambda:list(enumerate(self.s.get('model_names') or [])),lambda:self.s.get('model_index'),lambda key:self.app.action('select_model',key),enabled=lambda:self.s.get('connected') and not self.s.get('busy'),width=23).pack(side='right')
        self.button(self.content,'刷新耳机状态','refresh').pack(anchor='w',pady=(2,12))
        self.button(self.content,'退出 Enco Lite','quit',enabled=lambda:True).pack(anchor='w')
    def about(self):
        card=self.card_frame(self.content);self.label(card,'Enco Lite',style='Card.TLabel',font=('Microsoft YaHei UI',21,'bold')).pack(anchor='w')
        self.label(card,'让耳机控制回到简单。\n\nOPPO 耳机桌面助手\nv0.4.0-preview.2\nGPL-3.0-or-later\n\n协议与型号资料源自 OppoPodsManager。',style='Card.TLabel',justify='left').pack(anchor='w',pady=(14,0))
