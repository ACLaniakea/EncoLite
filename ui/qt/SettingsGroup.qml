import QtQuick
import QtQuick.Layouts
import "."
ColumnLayout {
    id: root
    property string title: ''
    property alias color: card.color
    default property alias content: card.content
    spacing: 8
    Layout.fillWidth: true
    Text { text: root.title; Layout.leftMargin: 2; font.pixelSize: 14; font.weight: Font.DemiBold; color: Theme.text }
    Card { id: card; Layout.fillWidth: true; padding: 14; contentSpacing: 6 }
}
