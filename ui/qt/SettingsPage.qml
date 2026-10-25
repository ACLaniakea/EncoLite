import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."
ColumnLayout {
    property var host
    spacing:17
    Text { text:'外观';font.pixelSize:14;font.weight:Font.DemiBold;color:Theme.text }
    Card {
        Layout.topMargin:-7
        objectName:'appearanceSettings'
        Layout.fillWidth:true
        SettingRow { title:'深浅外观';Layout.fillWidth:true
            UiSelect { accessibleName:'深浅外观';width:parent.width; options:[{value:'system',label:'跟随系统'},{value:'light',label:'浅色'},{value:'dark',label:'深色'}];value:backend.state.theme_mode||'system';onChosen:function(value){backend.action('change_theme_mode',[value]);} }
        }
        SettingRow { title:'主题色';Layout.fillWidth:true
            UiSelect { accessibleName:'主题色来源';width:parent.width;options:[{value:'custom',label:'自选颜色'},{value:'system',label:'跟随 Windows'}];value:backend.state.accent_mode||'custom';onChosen:function(value){backend.action('change_accent_mode',[value]);} }
        }
        RowLayout {
            visible:backend.state.accent_mode!=='system';Layout.fillWidth:true;spacing:6
            Repeater {
                model:[{color:'#168b51',name:'绿'},{color:'#0078d4',name:'蓝'},{color:'#7160d9',name:'紫'},{color:'#be4278',name:'玫红'},{color:'#c04b33',name:'珊瑚'},{color:'#986218',name:'琥珀'},{color:'#008184',name:'青'},{color:'#687080',name:'石墨'}]
                AbstractButton {
                    required property var modelData
                    property bool selected:backend.state.accent_color===modelData.color
                    Layout.preferredWidth:29;Layout.preferredHeight:29
                    Accessible.name:modelData.name+'色主题';ToolTip.visible:hovered;ToolTip.text:modelData.name
                    background:Rectangle{radius:8;color:'transparent';border.width:parent.selected||parent.visualFocus?2:0;border.color:Theme.text;Rectangle{anchors.fill:parent;anchors.margins:4;radius:5;color:modelData.color}}
                    onClicked:backend.action('change_accent_color',[modelData.color])
                }
            }
            Item{Layout.fillWidth:true}
            UiButton{text:'更多颜色';implicitWidth:88;onClicked:colorPicker.open()}
        }
    }
    Text { Layout.topMargin:7;text:'快捷控制';font.pixelSize:14;font.weight:Font.DemiBold;color:Theme.text }
    Card {
        Layout.topMargin:-7
        objectName:'quickSettings'
        Layout.fillWidth:true
        SettingRow { title:'始终置顶';controlWidth:42;Layout.fillWidth:true;UiSwitch{value:backend.state.quick_topmost!==false;Accessible.name:'快捷控制置顶';onTriggered:function(value){backend.action('change_quick_topmost',[value]);}} }
        SettingRow { title:'闲置后自动收起';controlWidth:42;Layout.fillWidth:true;UiSwitch{objectName:'quickAutoHide';value:!!backend.state.quick_auto_hide;Accessible.name:'快捷控制自动收起';onTriggered:function(value){backend.action('change_quick_auto_hide',[value]);}} }
        SettingRow {
            visible:!!backend.state.quick_auto_hide;title:'闲置时长';detail:'5–3600 秒';controlWidth:100;Layout.fillWidth:true
            RowLayout {
                width:parent.width;spacing:6
                TextField {
                    id:idleSeconds;objectName:'quickIdleSeconds';Layout.fillWidth:true;implicitHeight:35
                    font.pixelSize:13;color:Theme.text;selectByMouse:true;horizontalAlignment:TextInput.AlignHCenter
                    inputMethodHints:Qt.ImhDigitsOnly;validator:IntValidator{bottom:5;top:3600}
                    Accessible.name:'闲置秒数';property string draft:'';property bool dirty:false
                    Binding{target:idleSeconds;property:'text';value:String(backend.state.quick_idle_seconds||30);when:!idleSeconds.activeFocus&&!idleSeconds.dirty}
                    onTextEdited:{draft=text;dirty=true;}
                    onEditingFinished:{
                        if(dirty){var n=Number(draft),valid=/^\d+$/.test(draft)&&n>=5&&n<=3600;if(valid&&n!==(backend.state.quick_idle_seconds||30))backend.action('change_quick_idle_seconds',[n]);dirty=false;text=String(valid?n:(backend.state.quick_idle_seconds||30));}
                    }
                    background:Rectangle{radius:7;color:Theme.bg;border.color:idleSeconds.activeFocus?Theme.accent:Theme.line}
                }
                Text{text:'秒';font.pixelSize:13;color:Theme.muted}
            }
        }
        SettingRow { title:'连接时弹出提示';controlWidth:42;Layout.fillWidth:true;UiSwitch{value:!!backend.state.connection_popup;Accessible.name:'连接提示';onTriggered:function(value){backend.action('change_connection_popup',[value]);}} }
    }
    Text { Layout.topMargin:7;text:'启动与性能';font.pixelSize:14;font.weight:Font.DemiBold;color:Theme.text }
    Card {
        Layout.topMargin:-7
        objectName:'performanceSettings'
        Layout.fillWidth:true
        SettingRow { title:'开机自启动';detail:backend.state.autostart_error||'登录 Windows 后在托盘运行';controlWidth:42;Layout.fillWidth:true;UiSwitch{objectName:'autostartSwitch';value:!!backend.state.autostart_enabled;enabled:backend.state.autostart_available===true;Accessible.name:'开机自启动';onTriggered:function(value){backend.action('change_autostart',[value]);}} }
        SettingRow { title:'极速模式';detail:'关闭动画和阴影';controlWidth:42;Layout.fillWidth:true;UiSwitch{value:!!backend.state.fast_mode;Accessible.name:'极速模式';onTriggered:function(value){backend.action('change_fast_mode',[value]);}} }
        SettingRow { title:'快速唤出';detail:'保留界面进程，更快打开，占用更多内存';controlWidth:42;Layout.fillWidth:true;UiSwitch{value:!!backend.state.fast_launch;Accessible.name:'快速唤出';onTriggered:function(value){backend.action('change_fast_launch',[value]);}} }
    }
    Text { Layout.topMargin:7;text:'快捷键';font.pixelSize:14;font.weight:Font.DemiBold;color:Theme.text }
    Card {
        Layout.topMargin:-7
        objectName:'hotkeySettings'
        Layout.fillWidth:true
        SettingRow { title:'启用全局快捷键';detail:'在托盘运行时也可使用';controlWidth:42;Layout.fillWidth:true;UiSwitch{value:!!backend.hotkeys.enabled;enabled:!backend.hotkeys.capturing;Accessible.name:'启用全局快捷键';onTriggered:function(value){backend.action('set_hotkeys_enabled',[value]);}} }
        Repeater {
            model:backend.hotkeys.items||[]
            SettingRow {
                required property var modelData
                title:modelData.title; detail:modelData.error||'';controlWidth:224;Layout.fillWidth:true
                RowLayout {
                    width:parent.width;spacing:5
                    UiButton { text:modelData.label;Layout.fillWidth:true;enabled:!backend.hotkeys.capturing;onClicked:host.editHotkey(modelData) }
                    UiButton { text:'×';implicitWidth:28;enabled:!!modelData.binding&&!backend.hotkeys.capturing;Accessible.name:'清除'+modelData.title;onClicked:backend.saveHotkey(modelData.action,null) }
                }
            }
        }
    }
    Text { Layout.topMargin:7;text:'关于';font.pixelSize:14;font.weight:Font.DemiBold;color:Theme.text }
    Card {
        Layout.topMargin:-7
        objectName:'aboutSettings'
        Layout.fillWidth:true
        SettingRow{title:'Enco Lite';Layout.fillWidth:true;Text{text:'0.5.0-preview.13';font.pixelSize:13;color:Theme.muted}}
        SettingRow{title:'开源许可';Layout.fillWidth:true;Text{text:'GPL-3.0-or-later';font.pixelSize:13;color:Theme.muted}}
        SettingRow{title:'协议来源';Layout.fillWidth:true;Text{text:'OppoPodsManager';font.pixelSize:13;color:Theme.muted}}
    }
    UiButton{text:'退出 Enco Lite';onClicked:backend.action('quit',[])}
    AccentPicker{id:colorPicker}
}
