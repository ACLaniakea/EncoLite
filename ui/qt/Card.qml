import QtQuick
import QtQuick.Layouts
import "."
Rectangle {
    id: root
    property int padding: 16
    default property alias content: column.data
    implicitHeight: column.implicitHeight+padding*2
    radius: 11; color: Theme.material(Theme.card,Theme.dark?0.80:0.86,root.Window.window); border.color: Theme.line
    ColumnLayout { id: column; anchors.fill: parent; anchors.margins: root.padding; spacing: 14 }
    Behavior on color { ColorAnimation { duration: Theme.motion?150:0 } }
}
