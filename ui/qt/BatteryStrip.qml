import QtQuick
import QtQuick.Layouts
import "."
RowLayout {
    id: root
    property bool compact: false
    readonly property int controlHeight: compact?73:83
    implicitHeight: compact?73:83
    Layout.fillHeight: false
    Layout.minimumHeight: controlHeight
    Layout.preferredHeight: controlHeight
    Layout.maximumHeight: controlHeight
    spacing: 8
    Repeater {
        model: backend.state.battery_layout==='single'?[backend.state.single_battery_key||'left']:['left','case','right']
        Rectangle {
            required property string modelData
            Layout.fillWidth: true; Layout.fillHeight: true
            color: Theme.card; border.color: Theme.line; radius: 9
            ColumnLayout {
                anchors.fill: parent; anchors.margins: root.compact?10:12; spacing: 4
                Text { text: backend.state.battery_layout==='single'?'耳机':({left:'左耳',right:'右耳',case:'充电盒'})[modelData]; color: Theme.muted; font.pixelSize: 12 }
                RowLayout {
                    spacing: 3; Layout.fillWidth: true
                    Text { text: backend.state[modelData+'_value']||'—'; font.pixelSize: root.compact?20:23; font.weight: Font.DemiBold; color: Theme.text }
                    Image { visible: !!backend.state[modelData+'_charging']; source: 'icons/bolt.svg'; Layout.preferredWidth: 15; Layout.preferredHeight: 18; fillMode: Image.PreserveAspectFit; Accessible.name: "正在充电" }
                    Item { Layout.fillWidth: true }
                }
                Rectangle {
                    Layout.fillWidth: true; height: 3; radius: 2; color: Theme.line
                    Rectangle { height: 3; radius: 2; width: parent.width*Math.max(0,Math.min(1,Number(backend.state[modelData+'_level']||0))); color: Theme.accent }
                }
            }
        }
    }
}
