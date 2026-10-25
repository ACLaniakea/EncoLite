import QtQuick
import QtQuick.Layouts
import "."
import "Ui.js" as U
ColumnLayout {
    property var host
    spacing:15
    Text{text:'聆听模式';color:Theme.text;font.pixelSize:14;font.weight:Font.DemiBold}
    NoiseControl{Layout.fillWidth:true;Layout.preferredHeight:55}
    Card {
        Layout.fillWidth:true
        SoundControls{Layout.fillWidth:true}
        SettingRow{visible:!!backend.state.spatial_visible;title:'空间音频';Layout.fillWidth:true
            UiSelect{width:parent.width;accessibleName:'空间音频';options:U.options(backend.state.spatial_options);value:backend.state.spatial_mode;enabled:!!backend.state.connected&&!backend.state.busy;onChosen:function(value){backend.action('change_spatial',[value]);}}
        }
    }
    Item{Layout.fillHeight:true}
}
