import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

ApplicationWindow {
    id: root
    width: 864; height: 640
    visible: true
    title: "Enco Lite"
    color: "#f6f8f7"
    property int page: 0
    palette.accent: "#149c62"
    palette.highlight: "#149c62"
    font.family: "Microsoft YaHei UI"
    font.pixelSize: 14

    RowLayout {
        anchors.fill: parent
        spacing: 0
        Rectangle {
            Layout.preferredWidth: 176; Layout.fillHeight: true
            color: "#eef3f0"
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 16
                spacing: 8
                Label { text: "Enco Lite"; font.pixelSize: 23; font.bold: true; Layout.topMargin: 14; Layout.bottomMargin: 28 }
                Repeater {
                    model: ["我的耳机", "音效", "均衡器", "应用设置"]
                    Button {
                        required property int index
                        required property string modelData
                        text: modelData; flat: root.page !== index
                        highlighted: root.page === index
                        Layout.fillWidth: true; Layout.preferredHeight: 42
                        onClicked: root.page = index
                    }
                }
                Item { Layout.fillHeight: true }
                Button { text: "快捷控制"; flat: true; Layout.fillWidth: true }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; Layout.fillHeight: true
            Layout.margins: 25; spacing: 20
            Label { text: ["我的耳机", "音效", "均衡器", "应用设置"][root.page]; font.pixelSize: 26; font.bold: true }
            Loader {
                Layout.fillWidth: true; Layout.fillHeight: true
                sourceComponent: root.page === 2 ? eqPage : overviewPage
            }
        }
    }

    Component {
        id: overviewPage
        ColumnLayout {
            spacing: 18
            Rectangle {
                Layout.fillWidth: true; Layout.preferredHeight: 145
                radius: 12; color: "white"; border.color: "#e0e7e3"
                RowLayout {
                    anchors.fill: parent; anchors.margins: 20; spacing: 20
                    Image { source: productImage; sourceSize.width: 170; sourceSize.height: 170; fillMode: Image.PreserveAspectFit; Layout.preferredWidth: 125; Layout.fillHeight: true }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Label { text: "OPPO Enco X3"; font.pixelSize: 21; font.bold: true }
                        Label { text: "聆听，由你掌控"; color: "#65766c" }
                        RowLayout {
                            spacing: 18
                            Repeater {
                                model: ["左耳  85%", "右耳  90%", "充电盒  60%"]
                                Label { required property string modelData; text: modelData }
                            }
                        }
                    }
                }
            }
            Rectangle {
                Layout.fillWidth: true; Layout.preferredHeight: 166
                radius: 12; color: "white"; border.color: "#e0e7e3"
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 18; spacing: 14
                    Label { text: "聆听模式"; font.pixelSize: 17; font.bold: true }
                    RowLayout {
                        Layout.fillWidth: true; spacing: 8
                        Repeater {
                            model: ["降噪", "通透", "关闭"]
                            Button { required property int index; required property string modelData; text: modelData; highlighted: index === 0; Layout.fillWidth: true }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Label { text: "降噪强度"; Layout.fillWidth: true }
                        ComboBox { model: ["智能降噪", "深度降噪", "中度降噪", "轻度降噪"]; Layout.preferredWidth: 200 }
                    }
                }
            }
            Rectangle {
                Layout.fillWidth: true; Layout.preferredHeight: 124
                radius: 12; color: "white"; border.color: "#e0e7e3"
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 12
                    Switch { text: "佩戴检测"; checked: true; Layout.fillWidth: true }
                    Switch { text: "游戏模式"; Layout.fillWidth: true }
                }
            }
            Item { Layout.fillHeight: true }
        }
    }

    Component {
        id: eqPage
        Rectangle {
            radius: 12; color: "white"; border.color: "#e0e7e3"
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 22; spacing: 20
                Label { text: "自定义均衡器"; font.pixelSize: 19; font.bold: true }
                RowLayout {
                    Layout.fillWidth: true; Layout.fillHeight: true
                    Repeater {
                        model: ["64", "125", "250", "500", "1k", "2k", "4k", "8k"]
                        ColumnLayout {
                            required property string modelData
                            Layout.fillWidth: true
                            Label { text: Math.round(fader.value) + " dB"; Layout.alignment: Qt.AlignHCenter }
                            Slider { id: fader; orientation: Qt.Vertical; from: -6; to: 6; value: 0; Layout.fillHeight: true; Layout.alignment: Qt.AlignHCenter }
                            Label { text: modelData; Layout.alignment: Qt.AlignHCenter }
                        }
                    }
                }
                Button { text: "保存音效"; highlighted: true; Layout.alignment: Qt.AlignRight }
            }
        }
    }
}
