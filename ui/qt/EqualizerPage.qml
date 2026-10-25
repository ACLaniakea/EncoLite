import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."
import "Ui.js" as U
ColumnLayout {
    id: root
    property var host
    spacing: 15
    Text { visible: !backend.state.custom_available; text: "连接支持自定义音效的耳机后调整。"; color: Theme.muted; font.pixelSize: 13 }
    RowLayout {
        Layout.fillWidth: true; spacing: 12
        UiSelect { options: U.indexed(backend.state.custom_names); value: backend.state.custom_index; enabled: !!backend.state.custom_available&&!backend.state.busy; Layout.preferredWidth: 195; onChosen: function(value){backend.action('select_custom',[value]);} }
        TextField {
            id: eqName; Layout.fillWidth: true; implicitHeight: 35; maximumLength: 24
            color: Theme.text; font.pixelSize: 13; selectByMouse: true; placeholderText: "音效名称"
            enabled: !!backend.state.custom_available&&!backend.state.busy
            Binding { target: eqName; property: 'text'; value: backend.state.eq_name||''; when: !eqName.activeFocus }
            onTextEdited: backend.action('edit_custom_name',[text])
            background: Rectangle { color: Theme.card; radius: 7; border.color: eqName.activeFocus?Theme.accent:Theme.line }
        }
    }
    Card {
        Layout.fillWidth: true; implicitHeight: 319
        RowLayout { Layout.fillWidth: true; Text { text:"图示均衡器"; font.pixelSize:14; color:Theme.text; font.weight:Font.DemiBold } Item{Layout.fillWidth:true} Text { text:"dB"; font.pixelSize:12; color:Theme.muted } }
        Item {
            id: graph; Layout.fillWidth: true; Layout.fillHeight: true
            property real minimum: backend.state.eq_minimum===null||backend.state.eq_minimum===undefined?-6:Number(backend.state.eq_minimum)
            property real maximum: backend.state.eq_maximum===null||backend.state.eq_maximum===undefined?6:Number(backend.state.eq_maximum)
            property real span: Math.max(1,maximum-minimum)
            Item {
                anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 28
                Repeater {
                    model: U.ticks(graph.minimum,graph.maximum)
                    Text { required property real modelData; x:0; y:32+(graph.height-72)*(graph.maximum-modelData)/graph.span-height/2; text:U.gain(modelData); font.pixelSize:12; color:modelData===0?Theme.accent:Theme.muted }
                }
            }
            Item {
                anchors.fill: parent; anchors.leftMargin: 33; anchors.topMargin: 32; anchors.bottomMargin: 40
                Repeater {
                    model: U.ticks(graph.minimum,graph.maximum)
                    Rectangle { required property real modelData; width:parent.width; height:1; y:parent.height*(graph.maximum-modelData)/graph.span; color:modelData===0?Theme.accent:Theme.line; opacity:modelData===0?.5:1 }
                }
                RowLayout {
                    anchors.fill: parent; spacing: 3
                    Repeater {
                        model: backend.bandModel
                        Item {
                            required property int index
                            required property string label
                            required property real gain
                            Layout.fillWidth: true; Layout.fillHeight: true
                            Text { y:-29;anchors.horizontalCenter:parent.horizontalCenter;text: U.gain(fader.value); color:fader.value!==0?Theme.accent:Theme.muted; font.pixelSize:12 }
                            Slider {
                                id:fader; orientation:Qt.Vertical; from:graph.minimum; to:graph.maximum; stepSize:1
                                y:-6;height:parent.height+12;width:34;anchors.horizontalCenter:parent.horizontalCenter;topPadding:0;bottomPadding:0
                                enabled:!!backend.state.custom_available&&!backend.state.busy
                                Accessible.name:label+' 增益'
                                Binding { target:fader; property:'value'; value:gain; when:!fader.pressed }
                                onMoved:backend.action('edit_gain',[index,Math.round(value)])
                                background:Rectangle { x:(parent.width-width)/2; y:6; width:3; height:parent.height-12; radius:2; color:Theme.line
                                    Rectangle {width:3;color:Theme.accent;radius:2;y:Math.min((graph.maximum/graph.span),fader.visualPosition)*parent.height;height:Math.abs((graph.maximum/graph.span)-fader.visualPosition)*parent.height}
                                }
                                handle:Rectangle { x:(fader.width-width)/2; y:fader.topPadding+fader.visualPosition*(fader.availableHeight-height); width:24; height:12; radius:3; color:Theme.card; border.color:Theme.accent
                                    Rectangle { x:3; width:parent.width-6; height:1; anchors.verticalCenter:parent.verticalCenter; color:Theme.accent }
                                }
                                TapHandler { acceptedButtons:Qt.LeftButton; onDoubleTapped:{fader.value=0;backend.action('edit_gain',[index,0]);} }
                            }
                            Text { y:parent.height+12;anchors.horizontalCenter:parent.horizontalCenter;text:label.replace(' ','\n');font.pixelSize:11;lineHeight:1.2;horizontalAlignment:Text.AlignHCenter;color:Theme.muted }
                        }
                    }
                }
            }
        }
    }
    RowLayout {
        spacing: 9; Layout.fillWidth:true
        UiButton { text:"保存并使用"; primary:true; enabled:!!backend.state.custom_available&&!backend.state.busy; onClicked:{backend.action('edit_custom_name',[eqName.text]);backend.action('write_custom',['save']);} }
        UiButton { text:"试听修改"; enabled:!!backend.state.custom_available&&backend.state.custom_index>0&&!backend.state.busy; onClicked:backend.action('write_custom',['preview']) }
        UiButton { text:"删除音效"; enabled:!!backend.state.custom_available&&backend.state.custom_index>0&&!backend.state.busy; onClicked:host.ask('删除音效','从耳机中删除这个自定义音效？','write_custom',['delete']) }
    }
    Item { Layout.fillHeight: true }
}
