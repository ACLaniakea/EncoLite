import QtQuick
import QtQuick.Layouts
import "."
import "Ui.js" as U
ColumnLayout {
    property var host
    spacing: 14
    Card {
        Layout.fillWidth: true
        Repeater {
            model: backend.state.switches||[]
            SettingRow {
                required property var modelData
                Layout.fillWidth: true; title: modelData.title; controlWidth: 42
                detail: ['wear','long','hearing'].indexOf(modelData.key)>=0?modelData.detail:''
                UiSwitch { value: !!modelData.checked; enabled: !!modelData.enabled&&!backend.state.busy; Accessible.name: modelData.title; onTriggered: function(value){backend.action('change_feature',[modelData.key,value]);} }
            }
        }
        SettingRow {
            visible: (backend.state.game_options||[]).length>0; title: "游戏音效"; Layout.fillWidth: true
            UiSelect { width: parent.width; options: U.options(backend.state.game_options); value: backend.state.game_type; enabled: !backend.state.busy; onChosen: function(value){backend.action('change_game',[value]);} }
        }
        SettingRow {
            visible: !!backend.state.find_visible; title: "查找耳机"; detail: "取下耳机后播放提示音"; Layout.fillWidth: true; controlWidth: 108
            UiButton { width: parent.width; text: backend.state.finding?'停止提示音':'播放提示音'; enabled: !!backend.state.connected&&!backend.state.busy
                onClicked: backend.state.finding?backend.action('find_device',[false]):host.ask('播放提示音','请先取下耳机，再播放提示音。','find_device',[true]) }
        }
    }
    Item{Layout.fillHeight:true}
}
