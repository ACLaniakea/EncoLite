'use strict';
const bridge=window.chrome.webview;
const send=(type,values={})=>bridge.postMessage(JSON.stringify({type,...values}));
const action=(name,...args)=>send('action',{name,args});
const escapeHtml=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icons={buds:'<path d="M6 14V7a3 3 0 1 1 6 0v3M6 14v3a2 2 0 0 0 4 0v-6M16 10V7a3 3 0 1 1 6 0v5a3 3 0 0 1-3 3h-1v3"/>',noise:'<path d="M4 9v6m4-9v12m4-15v18m4-15v12m4-9v6"/>',transparency:'<path d="M4 9v6m4-9v12m8-12v12m4-9v6"/><path d="M11 9h2v6h-2"/>',off:'<path d="M4 12h16"/><path d="m9 7 6 10"/>',sound:'<path d="M5 9h4l5-4v14l-5-4H5zM18 8a6 6 0 0 1 0 8"/>',features:'<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="8" cy="6" r="2"/><circle cx="16" cy="12" r="2"/><circle cx="10" cy="18" r="2"/>',eq:'<path d="M5 4v16M12 4v16M19 4v16"/><path d="M3 8h4M10 15h4M17 10h4"/>',devices:'<rect x="3" y="4" width="12" height="12" rx="2"/><path d="M7 20h5M9 16v4"/><rect x="17" y="9" width="5" height="11" rx="1"/>',settings:'<path d="m10 3-1 3-3 1-3 3 2 3v3l3 1 2 4h4l2-4 3-1v-3l2-3-3-3-3-1-1-3z"/><circle cx="12" cy="12" r="3"/>',info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',close:'<path d="m5 5 14 14M19 5 5 19"/>',minimize:'<path d="M4 12h16"/>',maximize:'<rect x="5" y="5" width="14" height="14" rx="1"/>',bolt:'<path d="m13 2-9 12h7l-1 8 10-13h-7z"/>'};
const svg=(name,cls='')=>`<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${icons[name]||icons.buds}</svg>`;
const pages=[[0,'我的耳机','buds'],[1,'声音与音效','sound'],[4,'耳机功能','features'],[5,'自定义音效','eq'],[6,'连接的设备','devices'],[2,'应用设置','settings'],[3,'关于 Enco Lite','info']];
let H=null;
let S={},preferences={},view='main',page=0,signature='',picture='',fixture=false,rendered=false;
const app=document.querySelector('#app');
const colorMedia=matchMedia('(prefers-color-scheme: dark)');
const reducedMotionMedia=matchMedia('(prefers-reduced-motion: reduce)');
let lastMotion=null,surfaceAnimation=null,pageAnimation=null,modalAnimation=null;
const pendingSwitches=new Map();
const themeMode=()=>['system','light','dark'].includes(S.theme_mode)?S.theme_mode:(S.dark?'dark':'light');
const motionEnabled=()=>!S.fast_mode&&S.system_motion!==false&&!reducedMotionMedia.matches;
function applyAppearance(){
  const root=document.documentElement;
  root.classList.toggle('dark',themeMode()==='system'?colorMedia.matches:themeMode()==='dark');
  root.classList.toggle('fast-mode',!!S.fast_mode);
  root.classList.toggle('motion-off',!motionEnabled());
  if(!motionEnabled())for(const animation of document.getAnimations()){try{animation.finish()}catch{animation.cancel()}}
  if(lastMotion!==motionEnabled()){lastMotion=motionEnabled();send('window',{name:'motion',enabled:lastMotion})}
}
colorMedia.addEventListener('change',applyAppearance);
reducedMotionMedia.addEventListener('change',applyAppearance);
function animateElement(element,frames,duration,options={}){
  if(!element||!motionEnabled())return null;
  return element.animate(frames,{duration,easing:'cubic-bezier(.2,.75,.2,1)',...options});
}
function presentSurface(animate=true,native=false){
  surfaceAnimation?.cancel();app.classList.remove('dismissing');
  if(!animate||!motionEnabled()){app.classList.remove('in-motion');return}
  app.classList.add('in-motion');
  const animation=animateElement(app,[{opacity:native?1:0,transform:`translateY(${view==='notice'?12:8}px) scale(.985)`},{opacity:1,transform:'none'}],view==='main'?240:210);
  surfaceAnimation=animation;
  animation.finished.then(()=>{if(surfaceAnimation===animation){app.classList.remove('in-motion');surfaceAnimation=null}},()=>{});
}
function dismissSurface(token,native=false){
  cancelHotkeyEditor();closeChoice();
  surfaceAnimation?.cancel();app.classList.add('dismissing');
  if(!motionEnabled()){send('window',{name:'dismissed',token});return}
  app.classList.add('in-motion');
  const animation=animateElement(app,[{opacity:1,transform:'none'},{opacity:native?1:0,transform:'translateY(6px) scale(.985)'}],145,{fill:'forwards'});
  surfaceAnimation=animation;
  animation.finished.then(()=>{if(surfaceAnimation===animation)send('window',{name:'dismissed',token})},()=>{});
}
function reconcileSwitches(){
  for(const [key,pending] of pendingSwitches){
    const current=(S.switches||[]).find(item=>item.key===key);
    if(S.busy)pending.busySeen=true;
    if(!current||current.checked===pending.value||S.status_error||(!S.busy&&pending.busySeen)||performance.now()>pending.deadline){clearTimeout(pending.timer);pendingSwitches.delete(key)}
  }
}
const btn=(text,name,args=[],cls='')=>`<button class="${cls}" data-action="${name}" data-args="${escapeHtml(JSON.stringify(args))}">${escapeHtml(text)}</button>`;
const choiceLabels={anc:'降噪强度',presets:'耳机音效','all-noise':'聆听模式',spatial:'空间音频',game:'游戏音效',custom:'已保存的音效',theme:'外观',devices:'已配对的耳机',models:'耳机型号'};
const selected=(key,options,current,actionName,enabled=true)=>`<div class="select-control"><select hidden aria-hidden="true" tabindex="-1" data-select="${key}" data-change="${actionName}" ${enabled?'':'disabled'}>${options.map(([id,name])=>`<option value="${escapeHtml(id)}" ${String(id)===String(current)?'selected':''}>${escapeHtml(name)}</option>`).join('')}</select><button class="select-trigger" type="button" data-choice="${key}" role="combobox" aria-label="${choiceLabels[key]}" aria-haspopup="listbox" aria-expanded="false" aria-controls="choice-list"><span class="select-value"></span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 10 5 5 5-5"/></svg></button></div>`;
const modes=()=>S.noise_options||[];
const soundOptions=()=>[(modes().filter(x=>!['off','transparency','vocal'].includes(x.key))).map(x=>[x.key,x.name]),(S.presets||[]).map(x=>[x.id,x.name])];
const noise=()=>`<div class="noise" data-noise-container>${[['anc','降噪','noise'],['transparency','通透','transparency'],['off','关闭','off']].map(([key,title,icon])=>`<button data-noise="${key}" aria-label="${title}">${svg(icon)}<span>${title}</span></button>`).join('')}</div>`;
function listeningDetail(){
  const transparent=['transparency','vocal'].includes(S.noise);
  const options=modes().filter(item=>transparent?['transparency','vocal'].includes(item.key):!['off','transparency','vocal'].includes(item.key)).map(item=>[item.key,item.name]);
  return {label:transparent?'通透模式':'降噪强度',options,current:transparent?S.noise:S.anc_level,
    visible:!!S.connected&&!!S.noise&&S.noise!=='off'&&options.length>1,enabled:transparent?S.can_transparency:S.can_anc};
}
const sound=()=>`<div class="sound-rows"><div class="sound-row" data-mode-row><label data-mode-label>降噪强度</label>${selected('anc',soundOptions()[0],S.anc_level,'change_noise',S.can_anc)}</div><div class="sound-row" data-preset-row><label>耳机音效</label>${selected('presets',soundOptions()[1],S.preset,'change_preset',S.can_equalizer)}</div></div>`;
const batteries=()=>`<div class="batteries">${[['left','左耳'],['case','充电盒'],['right','右耳']].map(([key,name])=>`<div class="card battery" data-battery="${key}"><div class="battery-name">${name}</div><div class="battery-line"><span class="battery-value" data-text="${key}_value">—</span><svg class="charging" data-charging="${key}" viewBox="0 0 24 24" aria-label="正在充电">${icons.bolt}</svg></div><div class="battery-track"><div class="battery-fill" data-level="${key}"></div></div></div>`).join('')}</div>`;
const row=(title,detail,control)=>`<div class="card setting"><div class="setting-info"><div class="setting-title">${escapeHtml(title)}</div>${detail?`<div class="setting-detail">${escapeHtml(detail)}</div>`:''}</div>${control}</div>`;
const switchControl=(key,actionName,checked,enabled=true)=>`<input type="checkbox" class="switch" role="switch" aria-label="${escapeHtml(({fast_mode:'极速模式',connection_popup:'连接提示',hotkeys_enabled:'启用快捷键'})[key]||(S.switches||[]).find(x=>x.key===key)?.title||key)}" data-switch="${escapeHtml(key)}" data-change="${actionName}" ${checked?'checked':''} ${enabled?'':'disabled'}>`;
function titlebar(){return `<header class="titlebar" data-drag>${view==='quick'?'<img data-picture alt="">':''}<span class="caption">${view==='notice'?'耳机已连接':view==='quick'?escapeHtml(S.model_name||'未连接耳机'):'Enco Lite'}</span><div class="caption-controls">${view==='main'?`<button data-window="minimize" aria-label="最小化">${svg('minimize')}</button><button data-window="maximize" aria-label="最大化">${svg('maximize')}</button>`:''}<button class="close" data-window="close" aria-label="关闭">${svg('close')}</button></div></header>`;}
function overview(){return `<div class="stack"><div class="card hero"><img data-picture alt="耳机"><div class="hero-details"><div class="model" data-text="model_name"></div><div class="connection"><span class="dot ${S.connected?'connected':''}"></span><span data-connection></span></div><button class="primary connect-button" data-action="change_connection" data-connect></button></div></div>${batteries()}<section data-listening-section><div class="section-title">聆听模式</div>${noise()}</section>${sound()}</div>`;}
function sounds(){return `<div class="stack"><section data-listening-section><div class="section-title">聆听模式</div>${noise()}</section><div class="card">${sound()}</div></div>`;}
function features(){let html=row('聆听模式','',selected('all-noise',modes().map(x=>[x.key,x.name]),S.noise,'change_noise',S.connected));
if(S.spatial_visible)html+=row('空间音频','',selected('spatial',(S.spatial_options||[]).map(x=>[x.id,x.name]),S.spatial_mode,'change_spatial'));
html+=(S.switches||[]).map(x=>row(x.title,['wear','long','hearing'].includes(x.key)?x.detail:'',switchControl(x.key,'change_feature',x.checked,x.enabled))).join('');
if(S.game_options?.length)html+=row('游戏音效','',selected('game',S.game_options.map(x=>[x.id,x.name]),S.game_type,'change_game'));
if(S.find_visible)html+=row('查找耳机','取下耳机后播放提示音',btn(S.finding?'停止提示音':'播放提示音','find_device',[!S.finding]));
return `<div class="settings-group">${html}</div>`;}
const gainText=value=>`${value>0?'+':''}${value}`;
function equalizerGraph(){
  const bands=S.bands||[],minimum=Number(S.eq_minimum??-6),maximum=Number(S.eq_maximum??6),span=maximum-minimum;
  if(!bands.length||span<=0)return '<div class="card empty">连接耳机后显示可调频段。</div>';
  const step=span<=12?3:span<=24?6:12;
  const ticks=new Set([minimum,maximum]);
  for(let value=Math.ceil(minimum/step)*step;value<maximum;value+=step)ticks.add(value);
  if(minimum<=0&&maximum>=0)ticks.add(0);
  const levels=[...ticks].sort((a,b)=>b-a);
  const position=value=>100*(maximum-value)/span;
  return `<section class="card eq-console" aria-label="图示均衡器" style="--eq-bands:${bands.length}">
    <div class="eq-console-heading"><span>图示均衡器</span><span class="muted">dB</span></div>
    <div class="eq-readouts"><span></span><div class="eq-columns">${bands.map((band,index)=>`<output class="eq-readout" data-gain-value="${index}" for="band-${index}">${gainText(band.gain)}</output>`).join('')}</div></div>
    <div class="eq-graph">
      <div class="eq-axis" aria-hidden="true"><div>${levels.map(value=>`<span class="${value===0?'zero':''}" style="top:${position(value)}%">${gainText(value)}</span>`).join('')}</div></div>
      <div class="eq-plot">
        <div class="eq-grid" aria-hidden="true">${levels.map(value=>`<i class="${value===0?'zero':''}" style="top:${position(value)}%"></i>`).join('')}</div>
        <div class="eq-columns eq-faders">${bands.map((band,index)=>`<div class="eq-lane"><div class="eq-rail" aria-hidden="true"><div class="eq-fill"></div></div><input id="band-${index}" class="eq-fader" data-gain="${index}" type="range" step="1" min="${minimum}" max="${maximum}" value="${Number(band.gain)}" aria-label="${escapeHtml(band.label)} 增益" aria-orientation="vertical" title="双击归零" ${S.custom_available?'':'disabled'}></div>`).join('')}</div>
      </div>
    </div>
    <div class="eq-frequencies"><span></span><div class="eq-columns">${bands.map((band,index)=>{const [frequency,...unit]=String(band.label).split(' ');return `<label for="band-${index}"><span>${escapeHtml(frequency)}</span><small>${escapeHtml(unit.join(' '))}</small></label>`}).join('')}</div></div>
  </section>`;
}
function paintGain(input){
  const gain=Number(input.value),minimum=Number(input.min),maximum=Number(input.max),span=maximum-minimum;
  const readout=document.querySelector(`[data-gain-value="${input.dataset.gain}"]`);
  if(readout){readout.textContent=gainText(gain);readout.classList.toggle('is-adjusted',gain!==0)}
  input.setAttribute('aria-valuetext',`${gainText(gain)} dB`);
  if(span>0){
    const zero=100*(maximum-Math.max(minimum,Math.min(maximum,0)))/span,position=100*(maximum-gain)/span;
    const rail=input.closest('.eq-lane')?.querySelector('.eq-rail');
    if(rail){rail.style.setProperty('--eq-fill-top',`${Math.min(zero,position)}%`);rail.style.setProperty('--eq-fill-height',`${Math.abs(zero-position)}%`)}
  }
}
function equalizer(){return `<div class="stack">${S.custom_available?'':'<div class="empty card">此耳机暂不支持自定义音效，或尚未连接。</div>'}<div class="toolbar eq-toolbar">${selected('custom',(S.custom_names||[]).map((name,i)=>[i,name]),S.custom_index,'select_custom',S.custom_available)}<input class="grow" data-name type="text" aria-label="音效名称" maxlength="24" placeholder="音效名称" value="${escapeHtml(S.eq_name)}" ${S.custom_available?'':'disabled'}></div>${equalizerGraph()}<div class="toolbar">${btn('保存并使用','write_custom',['save'],'primary')}<button data-action="write_custom" data-args='["preview"]' title="试听会写入耳机中的当前音效">试听修改</button>${btn('删除音效','write_custom',['delete'])}</div></div>`;}
function devices(){return `<div class="stack"><div class="section-toolbar"><span class="section-title">${S.multi_available?'设备列表':'多设备连接'}</span>${btn('刷新','refresh')}</div>${(S.multi_devices||[]).map(x=>`<div class="card"><div class="device-name">${escapeHtml(x.name)}</div><div class="device-detail">${escapeHtml(x.detail)}</div>${S.multi_writable?`<div class="device-actions">${btn(x.connected?'断开':'连接','operate_multi',[x.connected?'disconnect':'connect',x.address])}${btn('优先连接','operate_multi',['priority',x.address])}${btn('取消配对','operate_multi',['unpair',x.address])}</div>`:''}</div>`).join('')}${!S.multi_devices?.length?`<div class="card empty">${S.multi_available?'没有其他已配对的设备':'连接支持多设备管理的耳机后查看设备'}</div>`:''}${S.multi_writable?`<div>${btn('自动连接优先级','operate_multi',['auto',''])}</div>`:''}</div>`;}
let hotkeyEditor=null,pendingHotkeyRequest=null,hotkeyRequestSerial=0;
const hotkeyLabel=value=>value?[...(value.modifiers&2?['Ctrl']:[]),...(value.modifiers&1?['Alt']:[]),...(value.modifiers&4?['Shift']:[]),value.key>=65&&value.key<=90||value.key>=48&&value.key<=57?String.fromCharCode(value.key):value.key>=112?`F${value.key-111}`:({32:'Space',33:'PageUp',34:'PageDown',35:'End',36:'Home',37:'←',38:'↑',39:'→',40:'↓',45:'Insert',46:'Delete'})[value.key]].join(' + '):'未设置';
function hotkeySettings(){
  if(!H)return '';
  return `<section class="hotkey-settings"><h2 class="section-title">快捷键</h2><div class="settings-group">${row('启用全局快捷键','在托盘运行时也可使用',switchControl('hotkeys_enabled','set_hotkeys_enabled',H.enabled))}${H.items.map(item=>`<div class="card setting hotkey-row" data-hotkey-row="${escapeHtml(item.action)}"><div class="setting-info"><div class="setting-title">${escapeHtml(item.title)}</div><div class="setting-detail hotkey-error" data-hotkey-error="${escapeHtml(item.action)}" role="status" hidden></div></div><div class="hotkey-controls"><button class="hotkey-binding" data-hotkey-edit="${escapeHtml(item.action)}" aria-label="设置${escapeHtml(item.title)}快捷键" title="点击修改"><span data-hotkey-value="${escapeHtml(item.action)}">${escapeHtml(item.label)}</span></button><button class="hotkey-clear" data-hotkey-clear="${escapeHtml(item.action)}" aria-label="清除${escapeHtml(item.title)}快捷键" title="清除">${svg('close')}</button></div></div>`).join('')}</div></section>`;
}
function updateHotkeys(){
  if(!H)return;
  const enabled=document.querySelector('[data-switch=hotkeys_enabled]');if(enabled){enabled.checked=H.enabled;enabled.disabled=!!H.capturing}
  for(const item of H.items){
    const value=document.querySelector(`[data-hotkey-value="${item.action}"]`);if(value){value.textContent=item.label;value.classList.toggle('unbound',!item.binding);value.parentElement.title=item.label+' · 点击修改';value.parentElement.setAttribute('aria-label',item.title+'，'+item.label+'，点击修改')}
    const clear=document.querySelector(`[data-hotkey-clear="${item.action}"]`);if(clear)clear.disabled=!item.binding||!!H.capturing;
    const error=document.querySelector(`[data-hotkey-error="${item.action}"]`);
    if(error){const message=item.error||'';error.textContent=message;error.hidden=!message}
  }
  if(hotkeyEditor){
    if(H.capturing)hotkeyEditor.hadCapture=true;
    else if(hotkeyEditor.hadCapture&&!hotkeyEditor.saving){cancelHotkeyEditor();return}
    const capture=document.querySelector('[data-hotkey-capture]');if(capture)capture.classList.toggle('ready',!!H.capturing);
    const save=document.querySelector('[data-hotkey-save]');if(save)save.disabled=hotkeyEditor.saving||!H.capturing;
  }
  if(pendingHotkeyRequest&&H.result?.request===pendingHotkeyRequest.request){
    pendingHotkeyRequest=null;
    if(hotkeyEditor){
      if(H.result.ok)cancelHotkeyEditor();
      else{hotkeyEditor.saving=false;document.querySelector('[data-hotkey-save]').disabled=false;document.querySelector('[data-hotkey-record-error]').textContent=H.result.error}
    }
  }
}
function openHotkeyEditor(name){
  const item=H?.items.find(item=>item.action===name);if(!item)return;
  closeChoice();modalAnimation?.cancel();confirmAction=null;
  hotkeyEditor={action:name,binding:item.binding,hadCapture:false,saving:false,focus:document.activeElement};
  const modal=document.querySelector('#confirmation');modal.hidden=false;modal.classList.remove('dismissing');
  modal.innerHTML=`<div class="dialog hotkey-dialog" role="dialog" aria-modal="true" aria-labelledby="hotkey-dialog-title"><h2 id="hotkey-dialog-title">${escapeHtml(item.title)}</h2><div class="hotkey-capture" data-hotkey-capture tabindex="0" aria-label="按下新的快捷键"><span data-hotkey-record-value>${escapeHtml(hotkeyLabel(item.binding))}</span></div><p class="hotkey-instruction">按下 Ctrl 或 Alt 与其他按键的组合</p><div class="hotkey-record-error" data-hotkey-record-error role="status" aria-live="polite"></div><div class="dialog-actions"><button data-hotkey-cancel>取消</button><button class="primary" data-hotkey-save disabled>保存</button></div></div>`;
  modal.querySelector('[data-hotkey-capture]').focus({preventScroll:true});
  modalAnimation=animateElement(modal.querySelector('.dialog'),[{opacity:0,transform:'translateY(6px) scale(.98)'},{opacity:1,transform:'none'}],145);
  action('begin_hotkey_capture');
}
function cancelHotkeyEditor(){
  if(!hotkeyEditor)return;
  const focus=hotkeyEditor.focus;hotkeyEditor=null;pendingHotkeyRequest=null;
  action('end_hotkey_capture');closeConfirmation();if(focus?.isConnected)focus.focus({preventScroll:true});
}
function saveHotkey(name,value){
  if(pendingHotkeyRequest)return;
  const request=`${Date.now()}-${++hotkeyRequestSerial}`;pendingHotkeyRequest={request,action:name};
  if(hotkeyEditor){hotkeyEditor.saving=true;document.querySelector('[data-hotkey-save]').disabled=true}
  action('set_hotkey',name,value,request);
}
function hotkeyFromEvent(event){
  if(event.metaKey)throw new Error('请使用 Ctrl 或 Alt 组合，不使用 Win 键');
  const modifiers=(event.altKey?1:0)|(event.ctrlKey?2:0)|(event.shiftKey?4:0);
  if(!(modifiers&3))throw new Error('请同时按住 Ctrl 或 Alt');
  const code=event.code;
  const key=/^Key[A-Z]$/.test(code)?code.charCodeAt(3):/^Digit[0-9]$/.test(code)?code.charCodeAt(5):/^F([1-9]|1[0-9]|2[0-4])$/.test(code)?111+Number(code.slice(1)):({Space:32,PageUp:33,PageDown:34,End:35,Home:36,ArrowLeft:37,ArrowUp:38,ArrowRight:39,ArrowDown:40,Insert:45,Delete:46})[code];
  if(!key||key===123)throw new Error('请选择字母、数字、方向键或功能键；F12 为系统保留键');
  if(modifiers===1&&key===115||modifiers===3&&key===46)throw new Error('这个组合由系统保留');
  return {modifiers,key};
}
document.addEventListener('keydown',event=>{
  if(!hotkeyEditor||event.isComposing)return;
  if(event.key==='Tab'&&!event.ctrlKey&&!event.altKey&&!event.metaKey){
    const controls=[...document.querySelectorAll('#confirmation [data-hotkey-capture],#confirmation button:not(:disabled)')];
    const index=controls.indexOf(document.activeElement);controls[(index+(event.shiftKey?-1:1)+controls.length)%controls.length]?.focus();event.preventDefault();event.stopImmediatePropagation();return;
  }
  if(event.key==='Enter'&&event.target.closest('button')&&!event.ctrlKey&&!event.altKey&&!event.metaKey)return;
  if(event.key===' '&&event.target.closest('button')&&!event.ctrlKey&&!event.altKey&&!event.metaKey)return;
  event.preventDefault();event.stopImmediatePropagation();
  if(event.key==='Escape'){cancelHotkeyEditor();return}
  if(event.repeat||hotkeyEditor.saving||!H?.capturing||['Control','Alt','Shift','Meta'].includes(event.key))return;
  const error=document.querySelector('[data-hotkey-record-error]');
  try{
    hotkeyEditor.binding=['Backspace','Delete'].includes(event.key)&&!event.ctrlKey&&!event.altKey&&!event.shiftKey?null:hotkeyFromEvent(event);
    document.querySelector('[data-hotkey-record-value]').textContent=hotkeyLabel(hotkeyEditor.binding);error.textContent='';
  }catch(reason){error.textContent=reason.message}
},true);

function settings(){return `<div class="stack settings-page"><section><h2 class="section-title">常规</h2><div class="settings-group">${row('外观','',selected('theme',[['system','跟随系统'],['light','浅色'],['dark','深色']],themeMode(),'change_theme_mode'))}${row('极速模式','关闭动画和阴影',switchControl('fast_mode','change_fast_mode',S.fast_mode))}${row('连接提示','连接耳机时显示',switchControl('connection_popup','change_connection_popup',S.connection_popup))}</div></section>${hotkeySettings()}<section><h2 class="section-title">设备</h2><div class="settings-group">${row('已配对的耳机',S.device_names?.length?'':'先在 Windows 蓝牙设置中配对',`<div class="inline-controls">${selected('devices',(S.device_names||[]).map((name,i)=>[i,name]),S.device_index,'select_device')}${btn('刷新','scan')}</div>`)}${row('耳机型号','识别不正确时可手动选择',selected('models',(S.model_names||[]).map((name,i)=>[i,name]),S.model_index,'select_model',S.connected))}</div></section><div class="toolbar settings-actions">${btn('刷新耳机状态','refresh')}${btn('退出 Enco Lite','quit')}</div></div>`;}
function about(){return `<div class="stack"><div class="card about-card"><div class="about-title">Enco Lite</div><div class="about-description">OPPO / 一加耳机桌面助手</div><dl class="about-properties"><div><dt>版本</dt><dd>0.4.0-preview.2</dd></div><div><dt>开源许可</dt><dd>GPL-3.0-or-later</dd></div><div><dt>协议来源</dt><dd>OppoPodsManager</dd></div></dl></div><div class="card device-properties"><div class="section-title">当前耳机</div><dl class="about-properties"><div><dt>型号</dt><dd data-text="model_name"></dd></div><div><dt>固件</dt><dd data-text="firmware"></dd></div><div><dt>连接信息</dt><dd data-device-details></dd></div></dl></div>${btn('打开快捷控制','show',['quick'])}</div>`;}
const renderers={0:overview,1:sounds,2:settings,3:about,4:features,5:equalizer,6:devices};
const layoutSignature=()=>JSON.stringify([view,page,!!H,S.connected,(S.switches||[]).map(x=>[x.key,x.title,x.detail]),S.spatial_options,S.game_options,S.find_visible,S.custom_available,(S.bands||[]).map(x=>x.label),S.eq_minimum,S.eq_maximum,S.multi_devices,S.multi_writable]);
function navigatePage(nextPage){
  if(nextPage===page||!renderers[nextPage])return;
  cancelHotkeyEditor();closeChoice();pageAnimation?.cancel();page=nextPage;
  const container=document.querySelector('.page');
  if(view!=='main'||!container){draw(true);return}
  document.querySelector('.heading').textContent=pages.find(item=>item[0]===page)[1];
  document.querySelectorAll('[data-page]').forEach(button=>button.classList.toggle('active',Number(button.dataset.page)===page));
  container.innerHTML=renderers[page]();container.scrollTop=0;signature=layoutSignature();update();
  pageAnimation=animateElement(container,[{opacity:.3,transform:'translateY(5px)'},{opacity:1,transform:'none'}],145);
}
function draw(force=false){
applyAppearance();
const next=layoutSignature();
if(force||signature!==next){closeChoice();signature=next;
if(view==='main')app.innerHTML=`<div class="main">${titlebar()}<div class="shell"><aside class="sidebar"><div class="brand">${svg('noise','brand-mark')}Enco Lite</div><nav class="nav">${pages.map(([id,title,icon])=>`<button data-page="${id}" class="${id===page?'active':''}">${svg(icon)}${title}</button>`).join('')}</nav><div class="sidebar-bottom">${btn('快捷控制','show',['quick'])}</div></aside><main class="workspace"><h1 class="heading">${pages.find(x=>x[0]===page)?.[1]||'我的耳机'}</h1><div class="page">${renderers[page]()}</div><footer class="status" data-status></footer></main></div></div>`;
else if(view==='quick')app.innerHTML=`<div class="quick">${titlebar()}<main class="quick-body">${batteries()}${noise()}${sound()}<div class="status" data-status></div>${btn('打开主窗口','show',['main'],'open-main')}</main></div>`;
else app.innerHTML=`<div class="notice">${titlebar()}<main class="notice-body"><div class="notice-info"><img data-picture alt=""><div><div class="model" data-text="model_name"></div><div class="metadata" data-notice-battery></div></div></div>${btn('打开快捷控制','show',['quick'],'open-main')}</main></div>`;
}update();rendered=true;
}
function update(){
document.querySelectorAll('[data-text]').forEach(el=>{el.textContent=S[el.dataset.text]??''});
document.querySelectorAll('[data-device-details]').forEach(el=>{el.textContent=String(S.device_info||'').split(' · ').filter(part=>part&&part!==S.firmware).join(' · ')||'—'});
document.querySelectorAll('[data-picture]').forEach(el=>{if(el.getAttribute('src')!==picture){if(picture)el.src=picture;else el.removeAttribute('src')}el.style.visibility=picture?'visible':'hidden'});
const singleBattery=S.battery_layout==='SingleBattery';
document.querySelectorAll('.batteries').forEach(el=>el.classList.toggle('single',singleBattery));
document.querySelectorAll('[data-battery]').forEach(el=>{const key=el.dataset.battery;el.hidden=singleBattery&&key!==(S.single_battery_key||'left');el.querySelector('.battery-name').textContent=singleBattery?'耳机':({left:'左耳',right:'右耳',case:'充电盒'})[key]});
document.querySelectorAll('[data-charging]').forEach(el=>el.toggleAttribute('hidden',!S[el.dataset.charging+'_charging']));
document.querySelectorAll('[data-level]').forEach(el=>el.style.width=`${Math.max(0,Math.min(100,Number(S[el.dataset.level+'_level']??0)*100))}%`);
document.querySelectorAll('[data-status]').forEach(el=>{el.textContent=S.status??'';el.classList.toggle('error',!!S.status_error)});
document.querySelectorAll('[data-connection]').forEach(el=>el.textContent=S.connecting?(S.cancelling?'正在取消…':'正在连接…'):S.connected?'已连接':'等待连接');
document.querySelectorAll('[data-connect]').forEach(el=>{el.textContent=S.connecting?(S.cancelling?'正在取消…':'取消连接'):S.connected?'断开控制连接':'连接耳机';el.disabled=!!S.busy&&!(S.connecting&&!S.cancelling)});
document.querySelectorAll('[data-noise]').forEach(el=>{const key=el.dataset.noise,mode=S.noise;el.classList.toggle('selected',key==='anc'?!!mode&&!['off','transparency','vocal'].includes(mode):key==='transparency'?['transparency','vocal'].includes(mode):mode==='off');el.disabled=!S['can_'+key]||!!S.busy});
document.querySelectorAll('[data-switch]').forEach(el=>{const key=el.dataset.switch,item=(S.switches||[]).find(x=>x.key===key),pending=pendingSwitches.get(key);el.checked=pending?pending.value:item?!!item.checked:!!S[key];el.disabled=item?(!item.enabled||!!S.busy||!!pending):false;el.classList.toggle('pending',!!pending)});
document.querySelectorAll('[data-notice-battery]').forEach(el=>el.textContent=[['left','左耳'],['right','右耳'],['case','盒']].filter(([k])=>S[k+'_value']&&S[k+'_value']!=='—').map(([k,n])=>n+' '+S[k+'_value']).join(' · '));
document.querySelectorAll('[data-action="find_device"]').forEach(el=>{el.textContent=S.finding?'停止提示音':'播放提示音';el.dataset.args=JSON.stringify([!S.finding])});
const detail=listeningDetail();
document.querySelectorAll('[data-listening-section],[data-noise-container]').forEach(el=>{el.hidden=!modes().length});
document.querySelectorAll('[data-preset-row]').forEach(el=>{el.hidden=!(S.presets||[]).length});
document.querySelectorAll('[data-mode-row]').forEach(el=>{el.hidden=!detail.visible});
document.querySelectorAll('[data-mode-label]').forEach(el=>{el.textContent=detail.label});
const choice={theme:[[['system','跟随系统'],['light','浅色'],['dark','深色']],themeMode(),true],anc:[detail.options,detail.current,detail.visible&&detail.enabled],presets:[soundOptions()[1],S.preset,S.can_equalizer],'all-noise':[modes().map(x=>[x.key,x.name]),S.noise,S.connected],spatial:[(S.spatial_options||[]).map(x=>[x.id,x.name]),S.spatial_mode,S.connected],game:[(S.game_options||[]).map(x=>[x.id,x.name]),S.game_type,S.connected],custom:[(S.custom_names||[]).map((n,i)=>[i,n]),S.custom_index,S.custom_available],devices:[(S.device_names||[]).map((n,i)=>[i,n]),S.device_index,true],models:[(S.model_names||[]).map((n,i)=>[i,n]),S.model_index,S.connected]};
document.querySelectorAll('[data-select]').forEach(el=>{const [values,current,enabled]=choice[el.dataset.select]||[[],null,false];const sig=JSON.stringify(values);if(el.dataset.options!==sig){el.innerHTML=values.map(([id,n])=>`<option value="${escapeHtml(id)}">${escapeHtml(n)}</option>`).join('');el.dataset.options=sig}if(el.value!==String(current))el.value=String(current);el.disabled=!enabled||(!!S.busy&&el.dataset.select!=='theme')||!values.length;syncChoice(el)});
document.querySelectorAll('[data-gain]').forEach(el=>{const index=Number(el.dataset.gain),gain=S.bands?.[index]?.gain??0;if(document.activeElement!==el)el.value=gain;el.disabled=!S.custom_available||!!S.busy;paintGain(el)});
const name=document.querySelector('[data-name]');if(name){if(document.activeElement!==name&&name.value!==(S.eq_name??''))name.value=S.eq_name??'';name.disabled=!S.custom_available||!!S.busy}
document.querySelectorAll('[data-action]').forEach(el=>{let disabled=false;const key=el.dataset.action,args=JSON.parse(el.dataset.args||'[]');if(['write_custom'].includes(key))disabled=!S.custom_available||S.busy||(args[0]!=='save'&&!(S.custom_index>0));else if(key==='find_device')disabled=S.busy||!S.connected;else if(key==='operate_multi')disabled=S.busy||!S.multi_writable||(args[0]==='priority'&&!S.multi_devices?.find(x=>x.address===args[1])?.connected);else if(!['show','quit','change_connection'].includes(key))disabled=!!S.busy;el.disabled=!!disabled});
updateHotkeys();
}
// One transient listbox, shared by every selector. Native selects retain the data/action contract.
let openChoice=null;
function syncChoice(select){
  const trigger=select.parentElement.querySelector('[data-choice]');
  if(select.dataset.select==='anc')trigger.setAttribute('aria-label',listeningDetail().label);
  trigger.querySelector('.select-value').textContent=select.selectedOptions[0]?.textContent||'暂无选项';
  trigger.disabled=select.disabled;
  if(openChoice?.select===select){
    if(select.disabled||openChoice.signature!==select.dataset.options)closeChoice();
    else for(const option of openChoice.list.querySelectorAll('[data-choice-option]')){
      option.setAttribute('aria-selected',String(select.options[Number(option.dataset.choiceOption)].selected));
    }
  }
}
function closeChoice(restoreFocus=false){
  if(!openChoice)return;
  const {trigger,popup}=openChoice;openChoice=null;
  trigger.setAttribute('aria-expanded','false');trigger.removeAttribute('aria-activedescendant');
  popup.remove();if(restoreFocus&&trigger.isConnected&&!trigger.disabled)trigger.focus({preventScroll:true});
}
function positionChoice(){
  if(!openChoice)return;
  const {trigger,popup,list,search}=openChoice,anchor=trigger.getBoundingClientRect(),margin=10,gap=5;
  const below=innerHeight-anchor.bottom-gap-margin,above=anchor.top-gap-margin;
  const desired=Math.min(300,Math.max(1,list.children.length)*36+12+(search?42:0));
  const down=below>=desired||below>=above;
  const height=Math.max(0,Math.min(desired,down?below:above));
  const width=Math.min(innerWidth-margin*2,Math.max(anchor.width,search?260:200));
  popup.style.width=`${width}px`;
  popup.style.left=`${Math.max(margin,Math.min(anchor.left,innerWidth-width-margin))}px`;
  list.style.maxHeight=`${Math.max(0,height-12-(search?42:0))}px`;
  popup.style.top=`${down?anchor.bottom+gap:Math.max(margin,anchor.top-gap-popup.offsetHeight)}px`;
  popup.dataset.side=down?'below':'above';
}
function activeChoice(index,scroll=true){
  if(!openChoice)return;
  const {list,trigger,search}=openChoice,options=[...list.querySelectorAll('[data-choice-option]')];
  openChoice.active=index;
  for(const option of options)option.classList.toggle('focused',Number(option.dataset.choiceOption)===index);
  const current=options.find(option=>Number(option.dataset.choiceOption)===index);
  for(const element of [list,trigger,search].filter(Boolean)){
    if(current)element.setAttribute('aria-activedescendant',current.id);else element.removeAttribute('aria-activedescendant');
  }
  if(scroll&&current)current.scrollIntoView({block:'nearest',behavior:'instant'});
}
function filterChoice(query=''){
  if(!openChoice)return;
  const {select,list,popup}=openChoice,needle=query.trim().toLocaleLowerCase();
  list.innerHTML=[...select.options].map((option,index)=>({option,index})).filter(({option})=>option.textContent.toLocaleLowerCase().includes(needle)).map(({option,index})=>`<button type="button" tabindex="-1" role="option" id="choice-option-${index}" class="choice-option" data-choice-option="${index}" aria-selected="${option.selected}" title="${escapeHtml(option.textContent)}"><span>${escapeHtml(option.textContent)}</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4 10-10"/></svg></button>`).join('');
  popup.querySelector('.choice-empty')?.remove();
  if(!list.children.length){const empty=document.createElement('div');empty.className='choice-empty';empty.textContent='没有匹配项';empty.setAttribute('role','status');popup.append(empty)}
  positionChoice();
  const selected=list.querySelector('[aria-selected=true]')||list.firstElementChild;
  activeChoice(selected?Number(selected.dataset.choiceOption):-1);
}
function toggleChoice(trigger){
  if(openChoice?.trigger===trigger){closeChoice(true);return}
  closeChoice();
  const select=trigger.parentElement.querySelector('select');if(select.disabled)return;
  const popup=document.createElement('div');popup.className='choice-popup';
  const searchable=select.options.length>12;
  popup.innerHTML=`${searchable?`<div class="choice-search"><input type="text" role="combobox" aria-expanded="true" aria-controls="choice-list" aria-autocomplete="list" aria-label="搜索${choiceLabels[select.dataset.select]}" placeholder="搜索${choiceLabels[select.dataset.select]}" autocomplete="off" spellcheck="false"></div>`:''}<div id="choice-list" class="choice-list" role="listbox" tabindex="-1" aria-label="${choiceLabels[select.dataset.select]}"></div>`;
  document.body.append(popup);
  openChoice={select,trigger,popup,list:popup.querySelector('.choice-list'),search:popup.querySelector('input'),signature:select.dataset.options,active:-1,typed:'',typedAt:0};
  trigger.setAttribute('aria-expanded','true');filterChoice();
  if(openChoice.search){openChoice.search.addEventListener('input',event=>filterChoice(event.target.value));openChoice.search.focus({preventScroll:true})}
  else openChoice.list.focus({preventScroll:true});
  popup.addEventListener('pointermove',event=>{const option=event.target.closest('[data-choice-option]');if(option)activeChoice(Number(option.dataset.choiceOption),false)});
  animateElement(popup,[{opacity:0,transform:`translateY(${popup.dataset.side==='below'?-3:3}px)`},{opacity:1,transform:'none'}],110);
}
function chooseOption(index){
  if(!openChoice||index<0)return;
  const {select}=openChoice;if(!select.options[index])return;
  const changed=select.selectedIndex!==index;
  select.selectedIndex=index;syncChoice(select);closeChoice(true);
  if(changed)select.dispatchEvent(new Event('change',{bubbles:true}));
}
document.addEventListener('pointerdown',event=>{if(openChoice&&!openChoice.popup.contains(event.target)&&!openChoice.trigger.contains(event.target))closeChoice()});
document.addEventListener('focusin',event=>{if(openChoice&&!openChoice.popup.contains(event.target)&&event.target!==openChoice.trigger)closeChoice()});
window.addEventListener('blur',()=>{closeChoice();cancelHotkeyEditor()});
window.addEventListener('resize',()=>closeChoice());
document.addEventListener('scroll',event=>{if(openChoice&&!openChoice.popup.contains(event.target))closeChoice()},true);
document.addEventListener('keydown',event=>{
  if(event.isComposing)return;
  if(!openChoice){
    const trigger=event.target.closest('[data-choice]');
    if(trigger&&!trigger.disabled&&['ArrowDown','ArrowUp','Home','End'].includes(event.key)){
      event.preventDefault();toggleChoice(trigger);
      if(event.key==='Home')activeChoice(0);else if(event.key==='End')activeChoice(openChoice.select.options.length-1);
    }
    return;
  }
  if(event.key==='Escape'){event.preventDefault();event.stopImmediatePropagation();closeChoice(true);return}
  if(event.key==='Tab'){closeChoice(true);return}
  const {list,search}=openChoice,indices=[...list.children].map(option=>Number(option.dataset.choiceOption));
  const position=indices.indexOf(openChoice.active),typing=event.target===search;
  if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)&&!(typing&&['Home','End'].includes(event.key))){
    event.preventDefault();
    const next=event.key==='Home'?0:event.key==='End'?indices.length-1:Math.max(0,Math.min(indices.length-1,position+(event.key==='ArrowDown'?1:-1)));
    activeChoice(indices[next]??-1);
  }else if(event.key==='Enter'||(event.key===' '&&!typing)){
    event.preventDefault();event.stopImmediatePropagation();chooseOption(openChoice.active);
  }else if(!typing&&event.key.length===1&&!event.ctrlKey&&!event.metaKey&&!event.altKey){
    event.preventDefault();const now=performance.now();
    openChoice.typed=(now-openChoice.typedAt>700?'':openChoice.typed)+event.key.toLocaleLowerCase();openChoice.typedAt=now;
    const matches=indices.find(index=>openChoice.select.options[index].textContent.toLocaleLowerCase().startsWith(openChoice.typed));
    if(matches!==undefined)activeChoice(matches);
  }
});
let confirmAction=null;
function confirm(title,description,callback){closeChoice();modalAnimation?.cancel();confirmAction=callback;const modal=document.querySelector('#confirmation');modal.hidden=false;modal.classList.remove('dismissing');modal.innerHTML=`<div class="dialog" role="dialog" aria-modal="true"><h2>${escapeHtml(title)}</h2><p>${escapeHtml(description)}</p><div class="dialog-actions"><button data-confirm="cancel">取消</button><button class="primary" data-confirm="yes">确认</button></div></div>`;modal.querySelector('[data-confirm=cancel]').focus();modalAnimation=animateElement(modal.querySelector('.dialog'),[{opacity:0,transform:'translateY(6px) scale(.98)'},{opacity:1,transform:'none'}],145);}
function closeConfirmation(){
  modalAnimation?.cancel();const modal=document.querySelector('#confirmation');modal.classList.add('dismissing');
  const animation=animateElement(modal.querySelector('.dialog'),[{opacity:1,transform:'none'},{opacity:0,transform:'translateY(3px) scale(.99)'}],95);
  modalAnimation=animation;
  if(animation)animation.finished.then(()=>{if(modalAnimation===animation)modal.hidden=true},()=>{});else modal.hidden=true;
}
document.addEventListener('click',event=>{const el=event.target.closest('button');if(!el||el.disabled)return;
if(el.dataset.hotkeyEdit){openHotkeyEditor(el.dataset.hotkeyEdit);return}
if(el.dataset.hotkeyClear){saveHotkey(el.dataset.hotkeyClear,null);return}
if(el.hasAttribute('data-hotkey-cancel')){cancelHotkeyEditor();return}
if(el.hasAttribute('data-hotkey-save')){if(hotkeyEditor&&!hotkeyEditor.saving&&H?.capturing)saveHotkey(hotkeyEditor.action,hotkeyEditor.binding);return}
if(el.dataset.choice){toggleChoice(el);return}
if(el.dataset.choiceOption!==undefined){chooseOption(Number(el.dataset.choiceOption));return}
if(el.dataset.confirm){const callback=confirmAction;confirmAction=null;closeConfirmation();if(el.dataset.confirm==='yes')callback?.();return}
if(el.dataset.page!==undefined){navigatePage(Number(el.dataset.page));send('window',{name:'page',page});return}
if(el.dataset.window){send('window',{name:el.dataset.window});return}
if(el.dataset.noise){if(el.dataset.noise==='transparency'&&['transparency','vocal'].includes(S.noise))return;action('change_noise',el.dataset.noise==='anc'?S.anc_level:el.dataset.noise);return}
if(el.dataset.action){const name=el.dataset.action,args=JSON.parse(el.dataset.args||'[]');const go=()=>{if(name==='write_custom')action('edit_custom_name',document.querySelector('[data-name]')?.value??S.eq_name??'');action(name,...args)};
if(name==='write_custom'&&args[0]==='delete')confirm('删除音效','删除当前自定义音效？',go);else if(name==='operate_multi'&&args[0]==='unpair')confirm('取消配对','从耳机的设备列表中取消此配对？',go);else go();}
});
document.addEventListener('change',event=>{const el=event.target;if(el.dataset.switch){if(el.dataset.change==='change_feature'){const key=el.dataset.switch;const pending={value:el.checked,busySeen:false,deadline:performance.now()+5000};pending.timer=setTimeout(()=>{if(pendingSwitches.get(key)===pending){pendingSwitches.delete(key);update()}},5000);pendingSwitches.set(key,pending);el.disabled=true;action('change_feature',key,el.checked)}else {if(el.dataset.switch==='fast_mode'){S.fast_mode=el.checked;applyAppearance()}action(el.dataset.change,el.checked)}}else if(el.dataset.select){const numeric=!['theme','anc','all-noise'].includes(el.dataset.select);action(el.dataset.change,numeric?Number(el.value):el.value)}else if(el.dataset.name!==undefined)action('edit_custom_name',el.value);else if(el.dataset.gain!==undefined)action('edit_gain',Number(el.dataset.gain),Number(el.value))});
document.addEventListener('input',event=>{const el=event.target;if(el.dataset.gain!==undefined)paintGain(el)});
document.addEventListener('mousedown',event=>{if(event.button===0&&event.target.closest('[data-drag]')&&!event.target.closest('button,input,select'))send('window',{name:'drag'})});
document.addEventListener('dblclick',event=>{const input=event.target.closest('[data-gain]');if(input&&!input.disabled){input.value=Math.max(Number(input.min),Math.min(Number(input.max),0));paintGain(input);action('edit_gain',Number(input.dataset.gain),Number(input.value));return}if(view==='main'&&event.target.closest('[data-drag]')&&!event.target.closest('button'))send('window',{name:'maximize'})});
document.addEventListener('keydown',event=>{if(event.isComposing)return;if(event.key==='Escape'){if(openChoice){event.preventDefault();closeChoice(true);return}if(!document.querySelector('#confirmation').hidden){confirmAction=null;closeConfirmation()}else send('window',{name:'close'})}});
document.addEventListener('mouseenter',()=>{if(view==='notice')send('window',{name:'hover',inside:true})});
document.addEventListener('mouseleave',()=>{if(view==='notice')send('window',{name:'hover',inside:false})});
const captures=new Map();let captureSerial=0;
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function capture(name){const id=++captureSerial;send('capture',{name,id});await new Promise(resolve=>{captures.set(id,resolve);setTimeout(resolve,1800)});}
async function inspect(id,test=false){try{for(const [number] of pages){page=number;draw(true);await wait(60);await capture(`page-${number}`)}page=0;draw(true);if(test){document.querySelector('[data-noise=off]').click();send('test_step',{name:'quick',id})}else send('diagnostic',{data:{id,result:'PASS',pages:pages.length,model:S.model_name,picture:S.product_picture,presets:S.presets?.length??0,switches:S.switches?.length??0,bands:S.bands?.length??0,devices:S.multi_devices?.length??0}})}catch(error){send('diagnostic',{data:{id,result:'FAIL',error:String(error)}})}}
bridge.addEventListener('message',event=>{const message=event.data;if(message.type==='state'){S=message.state||{};H=message.hotkeys||null;preferences=message.preferences||{};fixture=!!message.fixture;picture=message.picture||'';reconcileSwitches();draw()}else if(message.type==='init'){view=message.view;page=message.page??0;signature='';draw(true);send('ready',{view})}else if(message.type==='present')presentSurface(message.animate!==false,!!message.native);else if(message.type==='dismiss')dismissSurface(message.token,!!message.native);else if(message.type==='captured')captures.get(message.id)?.();else if(message.type==='inspect')inspect(message.id);else if(message.type==='test'&&fixture)inspect(message.id,true);else if(message.type==='click_noise'&&fixture)document.querySelector(`[data-noise="${message.mode}"]`)?.click();else if(message.type==='capture'&&fixture)capture(message.name)});
send('document_ready');
