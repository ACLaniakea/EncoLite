import QtQuick
import QtQuick.Layouts
import "."
import "Ui.js" as U
ColumnLayout {
    id: root
    property var host
    property bool manualModel: false
    spacing: 13
    Text{text:'当前耳机';color:Theme.text;font.pixelSize:14;font.weight:Font.DemiBold}
    Card {
        Layout.fillWidth:true
        SettingRow {title:'已配对的耳机';Layout.fillWidth:true;controlWidth:260
            UiSelect{width:parent.width;accessibleName:'已配对的耳机';options:U.indexed(backend.state.device_names);value:backend.state.device_index;enabled:!backend.state.busy;onChosen:function(value){backend.action('select_device',[value]);}}
        }
        RowLayout {
            Layout.fillWidth:true;spacing:9
            UiButton{text:'刷新耳机列表';quiet:true;enabled:!backend.state.busy;onClicked:backend.action('scan',[])}
            Item{Layout.fillWidth:true}
            UiButton{text:root.manualModel?'收起型号选择':'手动选择型号';quiet:true;enabled:!!backend.state.connected;onClicked:root.manualModel=!root.manualModel}
        }
        SettingRow{visible:root.manualModel;title:'耳机型号';Layout.fillWidth:true;controlWidth:260
            UiSelect{width:parent.width;accessibleName:'耳机型号';options:U.indexed(backend.state.model_names);value:backend.state.model_index;enabled:!!backend.state.connected&&!backend.state.busy;onChosen:function(value){backend.action('select_model',[value]);}}
        }
    }
    RowLayout { Layout.fillWidth:true;Layout.topMargin:4; Text { text:'多设备连接'; color:Theme.text; font.pixelSize:14; font.weight:Font.DemiBold } Item{Layout.fillWidth:true} UiButton {text:'刷新连接记录';quiet:true;enabled:!backend.state.busy;onClicked:backend.action('refresh',[])} }
    Repeater {
        model:backend.state.multi_devices||[]
        Card {
            required property var modelData
            Layout.fillWidth:true
            Text { text:modelData.name; color:Theme.text; font.pixelSize:15; font.weight:Font.DemiBold; Layout.fillWidth:true; elide:Text.ElideRight }
            Text { text:modelData.detail; color:Theme.muted; font.pixelSize:12; Layout.fillWidth:true; wrapMode:Text.Wrap }
            RowLayout {
                visible:!!backend.state.multi_writable; spacing:8
                UiButton { text:modelData.connected?'断开':'连接';enabled:!backend.state.busy;onClicked:backend.action('operate_multi',[modelData.connected?'disconnect':'connect',modelData.address]) }
                UiButton { text:'优先连接';enabled:!backend.state.busy&&modelData.connected;onClicked:backend.action('operate_multi',['priority',modelData.address]) }
                UiButton { text:'取消配对';enabled:!backend.state.busy;onClicked:host.ask('取消配对','从耳机中移除与“'+modelData.name+'”的配对？','operate_multi',['unpair',modelData.address]) }
            }
        }
    }
    Card { visible:!(backend.state.multi_devices||[]).length; Layout.fillWidth:true; Text { text:backend.state.multi_available?'没有其他已配对的设备':'连接支持多设备管理的耳机后查看设备';font.pixelSize:13;color:Theme.muted;wrapMode:Text.Wrap;Layout.fillWidth:true } }
    UiButton { visible:!!backend.state.multi_writable; text:'自动连接优先级';enabled:!backend.state.busy;onClicked:backend.action('operate_multi',['auto','']) }
    Item { Layout.fillHeight:true }
}
