import QtQuick
import QtQuick.Layouts
import "."
import "Ui.js" as U
RowLayout {
    id: root
    property bool compact: false
    readonly property int controlHeight: compact?51:55
    visible: (backend.state.noise_options||[]).length>0
    implicitHeight: compact?51:55
    Layout.fillHeight: false
    Layout.minimumHeight: controlHeight
    Layout.preferredHeight: controlHeight
    Layout.maximumHeight: controlHeight
    spacing: 8
    Repeater {
        model: [{key:'anc',title:'降噪',icon:'noise'},{key:'transparency',title:'通透',icon:'transparency'},{key:'off',title:'关闭',icon:'off'}]
        UiButton {
            required property var modelData
            Layout.fillWidth: true; Layout.fillHeight: true
            enabled: !!backend.state['can_'+modelData.key]&&!backend.state.busy
            selected: modelData.key==='anc'?!!backend.state.noise&&['off','transparency','vocal'].indexOf(backend.state.noise)<0:modelData.key==='transparency'?['transparency','vocal'].indexOf(backend.state.noise)>=0:backend.state.noise==='off'
            Accessible.name: modelData.title
            contentItem: RowLayout {
                spacing: 7
                Item { Layout.fillWidth: true }
                Image { source:'icons/'+modelData.icon+'.svg'; Layout.preferredWidth: 17; Layout.preferredHeight: 17 }
                Text { text: modelData.title; color: parent.parent.selected?Theme.accent:Theme.text; font.pixelSize: 14 }
                Item { Layout.fillWidth: true }
            }
            onClicked: backend.action('change_noise',[U.noise(backend.state,modelData.key)])
        }
    }
}
