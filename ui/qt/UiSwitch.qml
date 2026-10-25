import QtQuick
import QtQuick.Controls.Basic as C
import "."
C.AbstractButton {
    id: root
    property bool value: false
    signal triggered(bool value)
    implicitWidth: 42; implicitHeight: 24
    opacity: enabled ? 1 : .42
    Accessible.role: Accessible.CheckBox
    Accessible.checkable: true; Accessible.checked: value
    onClicked: triggered(!value)
    background: Rectangle {
        radius: height/2; color: root.value ? Theme.accent : Theme.line
        border.width: root.visualFocus ? 2 : 0; border.color: Theme.text
        Behavior on color { ColorAnimation { duration: Theme.motion ? 150 : 0 } }
        Rectangle {
            x: root.value ? parent.width-width-3 : 3; y: 3; width: 18; height: 18; radius: 9
            color: root.value ? Theme.accentText : Theme.card
            Behavior on x { NumberAnimation { duration: Theme.motion ? 160 : 0; easing.type: Easing.OutCubic } }
        }
    }
}
