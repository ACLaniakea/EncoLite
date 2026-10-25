import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

Popup {
    id: root
    objectName: 'accentPicker'
    parent: Overlay.overlay
    popupType: Popup.Item; modal: true; focus: true
    anchors.centerIn: parent; width: 330; padding: 20
    property real hue: 0.4
    property real saturation: 0.8
    property real brightness: 0.6
    readonly property color draft: Qt.hsva(hue,saturation,brightness,1)
    function setColor(value) {
        var color=Qt.color(value),r=color.r,g=color.g,b=color.b;
        var max=Math.max(r,g,b),min=Math.min(r,g,b),delta=max-min,h=0;
        if(delta>0){if(max===r)h=((g-b)/delta)%6;else if(max===g)h=(b-r)/delta+2;else h=(r-g)/delta+4;h/=6;if(h<0)h+=1;}
        if(delta>0)hue=h;saturation=max===0?0:delta/max;brightness=max;
    }
    onOpened:{setColor(backend.state.accent_mode==='system'?(backend.state.system_accent||'#168b51'):(backend.state.accent_color||'#168b51'));sv.forceActiveFocus();}
    background: Rectangle {radius:12;color:Theme.material(Theme.card,0.97,Window.window);border.color:Theme.line}
    contentItem: ColumnLayout {
        spacing:15
        Text {text:'自选主题色';font.pixelSize:18;font.weight:Font.DemiBold;color:Theme.text}
        Rectangle {
            id:sv;objectName:'accentSaturationValue';Layout.fillWidth:true;Layout.preferredHeight:155;color:Qt.hsva(root.hue,1,1,1)
            Rectangle {anchors.fill:parent;rotation:0;gradient:Gradient{orientation:Gradient.Horizontal;GradientStop{position:0;color:'white'}GradientStop{position:1;color:'transparent'}}}
            Rectangle {anchors.fill:parent;gradient:Gradient{GradientStop{position:0;color:'transparent'}GradientStop{position:1;color:'black'}}}
            Rectangle {x:root.saturation*(parent.width-1)-5;y:(1-root.brightness)*(parent.height-1)-5;width:10;height:10;radius:5;color:root.draft;border.width:2;border.color:'white'}
            MouseArea {anchors.fill:parent;Accessible.name:'颜色饱和度与亮度';function choose(mouse){root.saturation=Math.max(0,Math.min(1,mouse.x/width));root.brightness=1-Math.max(0,Math.min(1,mouse.y/height));}onPressed:function(mouse){sv.forceActiveFocus();choose(mouse)}onPositionChanged:function(mouse){if(pressed)choose(mouse)}}
        }
        Slider {
            id:hueSlider;objectName:'accentHue';Layout.fillWidth:true;from:0;to:1;value:root.hue;leftPadding:7;rightPadding:7
            Accessible.name:'色相';onMoved:root.hue=value;onPressedChanged:if(pressed)forceActiveFocus()
            background:Rectangle {x:7;y:(parent.height-height)/2;width:parent.width-14;height:12;radius:6;gradient:Gradient {orientation:Gradient.Horizontal;GradientStop{position:0;color:'#ff0000'}GradientStop{position:0.167;color:'#ffff00'}GradientStop{position:0.333;color:'#00ff00'}GradientStop{position:0.5;color:'#00ffff'}GradientStop{position:0.667;color:'#0000ff'}GradientStop{position:0.833;color:'#ff00ff'}GradientStop{position:1;color:'#ff0000'}}}
            handle:Rectangle {x:hueSlider.leftPadding+hueSlider.visualPosition*(hueSlider.availableWidth-width);y:(hueSlider.height-height)/2;width:16;height:20;radius:5;color:Qt.hsva(root.hue,1,1,1);border.color:Theme.text;border.width:2}
        }
        RowLayout {
            spacing:12
            Rectangle {Layout.preferredWidth:35;Layout.preferredHeight:35;radius:7;color:root.draft;border.color:Theme.line}
            TextField {
                id:hex;objectName:'accentHex';Layout.fillWidth:true;implicitHeight:35;font.pixelSize:13;color:Theme.text;selectByMouse:true;maximumLength:7
                Accessible.name:'颜色值';validator:RegularExpressionValidator{regularExpression:/#[0-9a-fA-F]{6}/}
                Binding{target:hex;property:'text';value:root.draft.toString().toUpperCase();when:!hex.activeFocus}
                onTextEdited:if(acceptableInput)root.setColor(text)
                background:Rectangle{radius:7;color:Theme.bg;border.color:hex.activeFocus?Theme.accent:Theme.line}
            }
        }
        RowLayout {
            Layout.alignment:Qt.AlignRight;spacing:8
            UiButton{text:'取消';onClicked:root.close()}
            UiButton{text:'应用';primary:true;enabled:!hex.activeFocus||hex.acceptableInput;onClicked:{backend.action('change_accent_color',[root.draft.toString()]);root.close();}}
        }
    }
}
