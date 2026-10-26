import QtQuick
import QtQuick.Controls.Basic as C
import "."
C.Button {
    id: root
    property bool primary: false
    property bool selected: false
    property bool quiet: false
    implicitWidth: Math.max(76, label.implicitWidth+24)
    implicitHeight: 35
    padding: 10
    font.pixelSize: 13
    opacity: enabled ? 1 : 0.42
    Accessible.name: text
    contentItem: Text {
        id: label; text: root.text; font: root.font; horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
        color: root.primary ? Theme.accentText : root.selected ? Theme.accent : Theme.text
    }
    background: Rectangle {
        objectName: 'buttonSurface'
        radius: 7
        color: root.primary ? (root.down?Qt.darker(Theme.accent,1.12):Theme.accent) : root.selected||root.hovered||root.down ? Theme.surface(Theme.selection,'selection',root.Window.window) : root.quiet ? "transparent" : Theme.surface(Theme.card,'field',root.Window.window)
        border.width: root.visualFocus ? 2 : 1
        border.color: root.visualFocus||root.selected ? Theme.accent : root.quiet||root.primary ? "transparent" : Theme.line
        Behavior on color { ColorAnimation { duration: Theme.motion ? 130 : 0 } }
    }
}
