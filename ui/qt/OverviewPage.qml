import QtQuick
import QtQuick.Layouts
import "."
ColumnLayout {
    id: root
    property var host
    spacing: 15
    Card {
        Layout.fillWidth: true; implicitHeight: 132
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 20
            Image { source: backend.picture; sourceSize.width: 180; sourceSize.height: 180; fillMode: Image.PreserveAspectFit; Layout.preferredWidth: 118; Layout.fillHeight: true }
            ColumnLayout {
                Layout.fillWidth: true; spacing: 9
                Text { text: backend.state.model_name||'未连接耳机'; font.pixelSize: 21; font.weight: Font.DemiBold; color: Theme.text; elide: Text.ElideRight; Layout.fillWidth: true }
                RowLayout {
                    spacing: 7
                    Rectangle { width: 6; height: 6; radius: 3; color: backend.state.connected?Theme.accent:Theme.muted }
                    Text { text: backend.state.connecting?(backend.state.cancelling?'正在取消…':'正在连接…'):backend.state.connected?'已连接':'等待连接'; font.pixelSize: 12; color: Theme.muted }
                }
                UiButton { text: backend.state.connecting?(backend.state.cancelling?'正在取消…':'取消连接'):backend.state.connected?'断开控制连接':'连接耳机'; primary: !backend.state.connected; enabled: !backend.state.busy||(backend.state.connecting&&!backend.state.cancelling); onClicked: backend.action('change_connection',[]) }
            }
        }
    }
    BatteryStrip { Layout.fillWidth: true; Layout.preferredHeight: 83 }
    Card {
        visible:!!backend.state.connected;Layout.fillWidth:true
        Text{text:'耳机信息';color:Theme.text;font.pixelSize:14;font.weight:Font.DemiBold}
        SettingRow{title:'固件';Layout.fillWidth:true;Text{text:backend.state.firmware||'—';color:Theme.muted;font.pixelSize:13}}
        Text{text:(backend.state.device_info||'').split(' · ').filter(function(part){return part!==String(backend.state.firmware||'');}).join(' · ');visible:text.length>0;color:Theme.muted;font.pixelSize:13;wrapMode:Text.Wrap;Layout.fillWidth:true}
    }
    Item { Layout.fillHeight: true }
}
