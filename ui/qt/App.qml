import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

Window {
    id: win
    property string kind: "main"
    property int page: 0
    property bool nativeGlass: false
    property bool systemFrame: false
    property real displayOpacity: 1
    opacity: 1
    property bool surfaceReady: !Theme.motion
    property bool materialChanging: false
    property bool restoreMaximized: false
    property bool closingUi: false
    property bool presented: false
    property real reveal: Theme.motion?0:1
    property int openDuration: 190
    property int closeDuration: 140
    readonly property bool transitioning: openAnimation.running||closeAnimation.running
    readonly property real surfaceScale: Theme.motion?1-(kind==='main'?0.005:0.01)*(1-reveal):1
    readonly property real surfaceOffset: Theme.motion?Math.min(2,height*0.002)*(1-reveal):0
    readonly property real contentScale: 1
    readonly property real contentOffset: 0
    readonly property bool quickMenuOpen:quickSound.menuOpen
    property bool maximized: visibility===Window.Maximized
    readonly property int sectionPage: page===5?1:page
    readonly property var pages: [{id:0,title:'耳机概览',icon:'buds'},{id:1,title:'声音',icon:'sound'},{id:4,title:'耳机功能',icon:'features'},{id:6,title:'设备',icon:'devices'},{id:2,title:'设置',icon:'settings'}]
    title: kind==='main'?'Enco Lite · 耳机助手':kind==='quick'?'Enco Lite · 快捷控制':'Enco Lite · 连接提示'
    width:kind==='main'?864:kind==='quick'?352:360
    height:kind==='main'?640:kind==='quick'?374:192
    minimumWidth:kind==='main'?740:width
    minimumHeight:kind==='main'?560:kind==='quick'?374:192
    maximumWidth:kind==='main'?16777215:kind==='quick'?352:360
    maximumHeight:kind==='main'?16777215:kind==='quick'?374:192
    flags: kind==='main'?Qt.Window|Qt.FramelessWindowHint:kind==='quick'?Qt.Tool|Qt.FramelessWindowHint|(backend.state.quick_topmost!==false?Qt.WindowStaysOnTopHint:0):Qt.Tool|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.WindowDoesNotAcceptFocus
    color:"transparent"
    signal finishedClosing()
    signal closeMenus()
    onClosing:function(event){event.accepted=false;backend.closeWindow(kind);}
    onActiveChanged:if(!active){closeMenus();if(hotkeyPopup.visible)hotkeyPopup.close();}
    onPageChanged:{closeMenus();if(page===3)page=2;}

    function present() {
        var minimized=visibility===Window.Minimized;
        var animate=!presented||closingUi||minimized;
        closeAnimation.stop();closingUi=false;
        // Duplicate tray/show requests must not snap an in-flight entrance.
        if(openAnimation.running&&!animate)return;
        if(animate&&Theme.motion){
            if(minimized){surfaceReady=false;displayOpacity=0;reveal=0;}
            openDuration=Math.max(70,Math.round((kind==='main'?190:170)*(1-reveal)));openAnimation.restart();
        }else if(!openAnimation.running){displayOpacity=1;reveal=1;surfaceReady=true;}
        presented=true;
    }
    function dismiss() {
        openAnimation.stop();closingUi=true;closeMenus();confirmPopup.close();hotkeyPopup.close();
        if(Theme.motion){closeDuration=Math.max(70,Math.round(140*reveal));closeAnimation.restart();}
        else finishedClosing();
    }
    function finishStalledEntrance() {
        if(presented&&!closingUi&&openAnimation.running&&reveal===0){
            openAnimation.stop();displayOpacity=1;reveal=1;surfaceReady=true;
        }
    }
    function navigate(index) { closeMenus();if(index!==page){page=index;} }
    function ask(title,description,name,args) {
        confirmPopup.heading=title;confirmPopup.description=description;confirmPopup.actionName=name;confirmPopup.arguments=args;confirmPopup.open();
    }
    function editHotkey(item) {
        hotkeyPopup.item=item;hotkeyPopup.candidate=item.binding;hotkeyPopup.keyLabel=item.label;
        hotkeyPopup.error='';hotkeyPopup.request='';hotkeyPopup.hadCapture=false;
        backend.action('begin_hotkey_capture',[]);hotkeyPopup.open();keyCapture.forceActiveFocus();
    }
    ParallelAnimation {
        id:openAnimation
        NumberAnimation{target:win;property:'displayOpacity';to:1;duration:win.openDuration;easing.type:Easing.OutCubic}
        NumberAnimation{target:win;property:'reveal';to:1;duration:win.openDuration;easing.type:Easing.OutCubic}
        onFinished:win.surfaceReady=true
    }
    ParallelAnimation {
        id:closeAnimation
        NumberAnimation{target:win;property:'displayOpacity';to:0;duration:win.closeDuration;easing.type:Easing.InCubic}
        NumberAnimation{target:win;property:'reveal';to:0;duration:win.closeDuration;easing.type:Easing.InCubic}
        onFinished:{win.surfaceReady=false;win.finishedClosing();}
    }
    Connections {
        target:Theme
        function onMotionChanged(){if(!Theme.motion){openAnimation.stop();closeAnimation.stop();win.displayOpacity=1;win.reveal=1;win.surfaceReady=true;if(win.closingUi)win.finishedClosing();}}
    }
    Connections {
        target:backend
        function onChanged(){
            if(!hotkeyPopup.visible)return;
            if(backend.hotkeys.capturing)hotkeyPopup.hadCapture=true;
            var result=backend.hotkeys.result;
            if(hotkeyPopup.request&&result&&result.request===hotkeyPopup.request){
                hotkeyPopup.request='';if(result.ok)hotkeyPopup.close();else hotkeyPopup.error=result.error||'无法保存快捷键';
            }else if(hotkeyPopup.hadCapture&&!backend.hotkeys.capturing&&!hotkeyPopup.request)hotkeyPopup.close();
        }
    }

    Rectangle {
        id:frame;anchors.fill:parent;radius:win.maximized||win.systemFrame?0:12;color:Theme.material(Theme.bg,Math.max(0.08,1-backend.glassTransparency/100),win);antialiasing:true
        objectName:'windowSurface'
        Behavior on color {enabled:!win.materialChanging&&!win.transitioning;ColorAnimation{duration:Theme.motion?150:0}}
        ColumnLayout {
            id:windowContent;objectName:'windowContent';anchors.fill:parent;anchors.margins:1;spacing:0
            opacity:win.displayOpacity
            transform:[
                Scale{origin.x:windowContent.width/2;origin.y:windowContent.height/2;xScale:win.surfaceScale;yScale:win.surfaceScale},
                Translate{y:win.surfaceOffset}
            ]
            Item {
                id:titleBar;Layout.fillWidth:true;Layout.preferredHeight:39
                DragHandler {target:null;acceptedButtons:Qt.LeftButton;onActiveChanged:if(active)win.startSystemMove()}
                TapHandler {acceptedButtons:Qt.LeftButton;onDoubleTapped:if(win.kind==='main')backend.maximize(win.kind)}
                RowLayout {
                    anchors.fill:parent;spacing:8
                    Image {visible:win.kind==='quick';source:backend.picture;sourceSize.width:48;sourceSize.height:48;Layout.preferredWidth:25;Layout.preferredHeight:25;Layout.leftMargin:12}
                    Text {text:win.kind==='main'?'Enco Lite':win.kind==='quick'?(backend.state.model_name||'未连接耳机'):'耳机已连接';font.pixelSize:12;color:Theme.muted;Layout.leftMargin:win.kind==='quick'?0:15;Layout.fillWidth:true;elide:Text.ElideRight}
                    Repeater {
                        model:win.kind==='main'?['minimize','maximize','close']:['close']
                        AbstractButton {
                            required property string modelData
                            Layout.preferredWidth:43;Layout.fillHeight:true
                            Accessible.name:modelData==='close'?'关闭':modelData==='minimize'?'最小化':'最大化'
                            background:Rectangle{color:parent.hovered?(parent.modelData==='close'?'#c94c48':Theme.selection):'transparent';topRightRadius:parent.modelData==='close'?Math.max(0,frame.radius-1):0}
                            contentItem:Item {
                                Rectangle {visible:modelData==='minimize';anchors.centerIn:parent;width:12;height:1;color:Theme.text}
                                Rectangle {visible:modelData==='maximize';anchors.centerIn:parent;width:10;height:10;color:'transparent';border.color:Theme.text}
                                Text {visible:modelData==='close';anchors.centerIn:parent;text:'×';font.pixelSize:22;color:Theme.text}
                            }
                            onClicked: modelData==='minimize'?backend.minimize(win.kind):modelData==='maximize'?backend.maximize(win.kind):backend.closeWindow(win.kind)
                        }
                    }
                }
            }

            Loader {
                active:win.kind==='main';visible:active;Layout.fillWidth:true;Layout.fillHeight:true
                sourceComponent:Component { RowLayout {
                anchors.fill:parent;spacing:0
                Rectangle {
                    color:Theme.material(Theme.sidebar,Theme.dark?0.32:0.24,win);bottomLeftRadius:Math.max(0,frame.radius-1)
                    Layout.preferredWidth:164;Layout.fillHeight:true
                    ColumnLayout {
                        anchors.fill:parent;anchors.margins:11;spacing:5
                        Item{Layout.preferredHeight:7}
                        Repeater {
                            model:win.pages.slice(0,4)
                            UiButton {
                                required property var modelData
                                Layout.fillWidth:true;implicitHeight:41;quiet:true;selected:win.sectionPage===modelData.id
                                Accessible.name:modelData.title
                                contentItem:RowLayout {
                                    spacing:10
                                    Image{source:'icons/'+modelData.icon+'.svg';Layout.preferredWidth:17;Layout.preferredHeight:17;Layout.leftMargin:10}
                                    Text{text:modelData.title;color:win.sectionPage===modelData.id?Theme.accent:Theme.text;font.pixelSize:13;Layout.fillWidth:true}
                                }
                                onClicked:win.sectionPage===modelData.id?win.closeMenus():win.navigate(modelData.id)
                            }
                        }
                        Item{Layout.fillHeight:true}
                        UiButton {
                            Layout.fillWidth:true;implicitHeight:41;quiet:true;selected:win.page===2
                            Accessible.name:'设置'
                            contentItem:RowLayout{
                                spacing:10
                                Image{source:'icons/settings.svg';Layout.preferredWidth:17;Layout.preferredHeight:17;Layout.leftMargin:10}
                                Text{text:'设置';color:win.page===2?Theme.accent:Theme.text;font.pixelSize:13;Layout.fillWidth:true}
                            }
                            onClicked:win.navigate(2)
                        }
                        Rectangle{Layout.fillWidth:true;Layout.preferredHeight:1;Layout.topMargin:5;Layout.bottomMargin:5;color:Theme.line}
                        UiButton{text:'快捷控制';quiet:true;Layout.fillWidth:true;onClicked:backend.show('quick')}
                    }
                }
                ColumnLayout {
                    Layout.fillWidth:true;Layout.fillHeight:true;Layout.margins:22;spacing:16
                    Text {text:(win.pages.find(function(p){return p.id===win.sectionPage;})||win.pages[0]).title;font.pixelSize:23;font.weight:Font.DemiBold;color:Theme.text}
                    RowLayout {
                        visible:win.sectionPage===1;Layout.fillWidth:true;spacing:6
                        UiButton{text:'聆听与音效';selected:win.page===1;quiet:true;onClicked:win.navigate(1)}
                        UiButton{text:'均衡器';selected:win.page===5;quiet:true;onClicked:win.navigate(5)}
                        Item{Layout.fillWidth:true}
                    }
                    ScrollView {
                        id:scroll;Layout.fillWidth:true;Layout.fillHeight:true;clip:true
                        contentWidth:availableWidth
                        ScrollBar.horizontal.policy:ScrollBar.AlwaysOff
                        ScrollBar.vertical.policy:ScrollBar.AsNeeded
                        Loader {
                            id:pageLoader;width:scroll.availableWidth;active:win.kind==='main'
                            height:Math.max(implicitHeight,scroll.availableHeight)
                            sourceComponent:win.page===1?sounds:win.page===5?equalizer:win.page===4?features:win.page===6?devices:win.page===2?settings:overview
                            onLoaded:{item.host=win;scroll.contentItem.contentY=0;if(Theme.motion)pageFade.restart();}
                            NumberAnimation {id:pageFade;target:pageLoader;property:'opacity';from:0;to:1;duration:145;running:false}
                        }
                    }
                    Text {text:backend.state.status||'';font.pixelSize:12;color:backend.state.status_error?Theme.error:Theme.muted;elide:Text.ElideRight;Layout.fillWidth:true;Layout.preferredHeight:17}
                }
            }
                } }
            ColumnLayout {
                visible:win.kind==='quick';Layout.fillWidth:true;Layout.fillHeight:true;Layout.margins:15;Layout.topMargin:4;spacing:12
                BatteryStrip{compact:true;Layout.fillWidth:true;Layout.preferredHeight:73}
                NoiseControl{compact:true;Layout.fillWidth:true;Layout.preferredHeight:51}
                SoundControls{id:quickSound;compact:true;Layout.fillWidth:true}
                Text{text:backend.state.status||'';font.pixelSize:12;color:backend.state.status_error?Theme.error:Theme.muted;Layout.fillWidth:true;elide:Text.ElideRight}
                Item{Layout.fillHeight:true}
                UiButton{text:'打开主窗口';Layout.fillWidth:true;onClicked:backend.show('main')}
            }
            ColumnLayout {
                visible:win.kind==='notice';Layout.fillWidth:true;Layout.fillHeight:true;Layout.margins:15;Layout.topMargin:0;spacing:12
                RowLayout {
                    Layout.fillWidth:true;spacing:13
                    Image{source:backend.picture;sourceSize.width:120;sourceSize.height:120;Layout.preferredWidth:61;Layout.preferredHeight:61;fillMode:Image.PreserveAspectFit}
                    ColumnLayout {
                        Layout.fillWidth:true;spacing:7
                        Text{text:backend.state.model_name||'';color:Theme.text;font.pixelSize:16;font.weight:Font.DemiBold;Layout.fillWidth:true;elide:Text.ElideRight}
                        RowLayout {
                            Layout.fillWidth:true;spacing:8
                            Repeater {
                                model:['left','right','case'].filter(function(k){return backend.state[k+'_value']&&backend.state[k+'_value']!=='—';})
                                Text {
                                    required property string modelData
                                    objectName:'noticeBattery_'+modelData
                                    text:({left:'左',right:'右',case:'盒'})[modelData]+' '+backend.state[modelData+'_value']
                                    color:Theme.batteryLow(modelData)?Theme.error:Theme.muted;font.pixelSize:12
                                }
                            }
                            Item{Layout.fillWidth:true}
                        }
                    }
                }
                UiButton{text:'打开快捷控制';Layout.fillWidth:true;onClicked:backend.show('quick')}
            }
        }
        HoverHandler {enabled:win.kind==='notice';onHoveredChanged:backend.hoverNotice(hovered)}
        // Paint the outline after content so sidebar/hover fills cannot cover it.
        Rectangle {
            objectName:'windowOutline';anchors.fill:parent;z:100;radius:frame.radius;visible:!win.systemFrame
            color:'transparent';antialiasing:true
            border.width:1;border.color:Theme.line;border.pixelAligned:false
        }
    }
    Repeater {
        model:win.kind==='main'&&!win.maximized?[Qt.LeftEdge,Qt.RightEdge,Qt.TopEdge,Qt.BottomEdge,Qt.LeftEdge|Qt.TopEdge,Qt.RightEdge|Qt.TopEdge,Qt.LeftEdge|Qt.BottomEdge,Qt.RightEdge|Qt.BottomEdge]:[]
        MouseArea {
            required property int modelData
            property bool horizontal:(modelData&(Qt.LeftEdge|Qt.RightEdge))!==0
            property bool vertical:(modelData&(Qt.TopEdge|Qt.BottomEdge))!==0
            x:modelData&Qt.RightEdge?win.width-width:0;y:modelData&Qt.BottomEdge?win.height-height:0
            width:horizontal?6:win.width;height:vertical?6:win.height
            cursorShape:horizontal&&vertical?(modelData===(Qt.LeftEdge|Qt.TopEdge)||modelData===(Qt.RightEdge|Qt.BottomEdge)?Qt.SizeFDiagCursor:Qt.SizeBDiagCursor):horizontal?Qt.SizeHorCursor:Qt.SizeVerCursor
            onPressed:win.startSystemResize(modelData)
        }
    }

    Component{id:overview;OverviewPage{}}
    Component{id:sounds;SoundsPage{}}
    Component{id:features;FeaturesPage{}}
    Component{id:equalizer;EqualizerPage{}}
    Component{id:devices;DevicesPage{}}
    Component{id:settings;SettingsPage{}}

    Popup {
        id:confirmPopup;parent:Overlay.overlay;popupType:Popup.Item;modal:true;focus:true
        anchors.centerIn:parent;width:Math.min(360,parent?parent.width-30:360);padding:22
        property string heading:'';property string description:'';property string actionName:'';property var arguments:[]
        background:Rectangle{objectName:'dialogSurface';radius:12;color:Theme.surface(Theme.card,'menu',win);border.color:Theme.line}
        contentItem:ColumnLayout {
            spacing:15
            Text{text:confirmPopup.heading;font.pixelSize:18;font.weight:Font.DemiBold;color:Theme.text}
            Text{text:confirmPopup.description;font.pixelSize:13;color:Theme.muted;wrapMode:Text.Wrap;Layout.fillWidth:true}
            RowLayout{Layout.alignment:Qt.AlignRight;spacing:8;UiButton{text:'取消';onClicked:confirmPopup.close()}UiButton{text:'确认';primary:true;onClicked:{backend.action(confirmPopup.actionName,confirmPopup.arguments);confirmPopup.close();}}}
        }
    }
    Popup {
        id:hotkeyPopup;parent:Overlay.overlay;popupType:Popup.Item;modal:true;focus:true
        anchors.centerIn:parent;width:Math.min(370,parent?parent.width-30:370);padding:22
        property var item:({})
        property var candidate:null
        property string keyLabel:'未设置'
        property string error:''
        property string request:''
        property bool hadCapture:false
        onClosed:backend.action('end_hotkey_capture',[])
        background:Rectangle{objectName:'dialogSurface';radius:12;color:Theme.surface(Theme.card,'menu',win);border.color:Theme.line}
        contentItem:ColumnLayout {
            spacing:15
            Text{text:hotkeyPopup.item.title||'设置快捷键';font.pixelSize:18;font.weight:Font.DemiBold;color:Theme.text;Layout.fillWidth:true;wrapMode:Text.Wrap}
            Rectangle {
                id:keyCapture;objectName:'fieldSurface';Layout.fillWidth:true;implicitHeight:67;radius:9;color:Theme.surface(Theme.bg,'field',win);border.color:backend.hotkeys.capturing?Theme.accent:Theme.line
                focus:true;activeFocusOnTab:true;Accessible.name:'按下新的快捷键'
                Text{anchors.centerIn:parent;text:hotkeyPopup.keyLabel;color:Theme.text;font.pixelSize:17;font.weight:Font.DemiBold}
                Keys.onPressed:function(event){
                    if(event.key===Qt.Key_Tab){event.accepted=false;return;}
                    event.accepted=true;
                    if(event.key===Qt.Key_Escape){hotkeyPopup.close();return;}
                    if(event.isAutoRepeat||hotkeyPopup.request||!backend.hotkeys.capturing)return;
                    var result=backend.captureKey(event.key,event.modifiers);
                    if(result.ignore)return;
                    hotkeyPopup.error=result.error||'';
                    if(!result.error){hotkeyPopup.candidate=result.binding;hotkeyPopup.keyLabel=result.label;}
                }
            }
            Text{text:'按下 Ctrl 或 Alt 与其他按键的组合';font.pixelSize:12;color:Theme.muted;Layout.fillWidth:true;wrapMode:Text.Wrap}
            Text{visible:hotkeyPopup.error.length>0;text:hotkeyPopup.error;font.pixelSize:12;color:Theme.error;Layout.fillWidth:true;wrapMode:Text.Wrap}
            RowLayout {
                Layout.alignment:Qt.AlignRight;spacing:8
                UiButton{text:'取消';onClicked:hotkeyPopup.close()}
                UiButton{text:'保存';primary:true;enabled:!!backend.hotkeys.capturing&&!hotkeyPopup.request&&!hotkeyPopup.error;onClicked:hotkeyPopup.request=backend.saveHotkey(hotkeyPopup.item.action,hotkeyPopup.candidate)}
            }
        }
    }
}
