import QtQuick
import QtQuick.Layouts
import "."
RowLayout {
    id: root
    property string title: ""
    property string detail: ""
    property int controlWidth: 200
    default property alias controls: control.data
    spacing: 16
    implicitHeight: Math.max(labels.implicitHeight,control.childrenRect.height)+12
    ColumnLayout {
        id: labels; Layout.fillWidth: true; spacing: 4
        Text { text: root.title; font.pixelSize: 13; color: Theme.text; wrapMode: Text.Wrap; Layout.fillWidth: true }
        Text { visible: text.length>0; text: root.detail; font.pixelSize: 12; color: Theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
    }
    Item { id: control; Layout.preferredWidth: root.controlWidth; Layout.preferredHeight: childrenRect.height }
}
