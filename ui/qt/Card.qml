import QtQuick
import QtQuick.Layouts
import "."
Rectangle {
    id: root
    property int padding: 16
    property int contentSpacing: 14
    default property alias content: column.data
    implicitHeight: column.implicitHeight+padding*2
    objectName: 'cardSurface'
    radius: 11; color: Theme.surface(Theme.card,'card',root.Window.window); border.color: Theme.line
    ColumnLayout { id: column; anchors.fill: parent; anchors.margins: root.padding; spacing: root.contentSpacing }
    Behavior on color { ColorAnimation { duration: Theme.motion?150:0 } }
}
