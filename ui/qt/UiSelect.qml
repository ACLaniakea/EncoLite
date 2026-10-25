import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."
Item {
    id: root
    property var options: []
    property var value: null
    property string accessibleName: "选项"
    property var choices: []
    property string signature: ""
    property bool searchable: choices.length>12
    readonly property Item menuLayer: Overlay.overlay
    readonly property bool popupVisible: popup.visible
    signal chosen(var value)
    implicitWidth: 200; implicitHeight: 35
    function rebuild() {
        var next=JSON.stringify(options||[]);
        if(next!==signature){ popup.close(); choices=options||[]; signature=next; }
    }
    function filtered() {
        var query=search.text.toLocaleLowerCase();
        return choices.filter(function(row){return String(row.label).toLocaleLowerCase().indexOf(query)>=0;});
    }
    function openMenu() {
        if(!root.enabled||!root.visible||!choices.length||popup.visible||!menuLayer)return;
        var window=root.Window.window;
        if(window&&typeof window.closeMenus==='function')window.closeMenus();
        search.text=""; list.currentIndex=Math.max(0,choices.findIndex(function(row){return row.value===root.value;}));
        var point=root.mapToItem(menuLayer,0,0);
        var x=Math.max(8,Math.min(point.x,menuLayer.width-popup.width-8));
        var y=point.y+root.height+5;
        if(y+popup.implicitHeight>menuLayer.height-8)y=Math.max(8,point.y-popup.implicitHeight-5);
        var local=menuLayer.mapToItem(root,x,y);popup.x=local.x;popup.y=local.y;
        popup.open(); if(searchable)search.forceActiveFocus();else list.forceActiveFocus();
    }
    function closeMenu() { popup.close(); }
    function toggleMenu() { popup.visible?popup.close():root.openMenu(); }
    function pick(index) { var row=list.model[index];if(row){popup.close();root.chosen(row.value);trigger.forceActiveFocus();} }
    onOptionsChanged: rebuild()
    onEnabledChanged: if(!enabled)popup.close()
    onVisibleChanged: if(!visible)popup.close()
    Component.onCompleted: rebuild()
    Component.onDestruction: if(popup)popup.close()
    Connections {
        target: root.Window.window; ignoreUnknownSignals: true
        function onCloseMenus() { popup.close(); }
    }
    UiButton {
        id: trigger; anchors.fill: parent; padding: 0
        Accessible.name: root.accessibleName
        objectName: 'selectTrigger'
        onClicked: root.toggleMenu()
        contentItem: RowLayout {
            spacing: 9
            Text { Layout.fillWidth: true; Layout.leftMargin: 11; elide: Text.ElideRight; color: Theme.text; font.pixelSize: 13
                text: {var row=root.choices.find(function(row){return row.value===root.value;});return row?row.label:"请选择";} }
            Text { text: "⌄"; color: Theme.muted; font.pixelSize: 17; Layout.rightMargin: 10; Layout.bottomMargin: 3 }
        }
        Keys.onPressed: function(event){if(event.key===Qt.Key_Down||event.key===Qt.Key_Space){root.openMenu();event.accepted=true;}}
    }
    Popup {
        id: popup; parent: root; popupType: Popup.Item
        objectName: 'selectPopup'
        width: Math.min(Math.max(root.width,160),root.menuLayer?root.menuLayer.width-16:root.width)
        implicitHeight: Math.min(300, root.choices.length*35+(root.searchable?46:0)+12)
        padding: 6; closePolicy: Popup.CloseOnEscape|Popup.CloseOnPressOutsideParent
        focus: true
        background: Rectangle { color: Theme.card; border.color: Theme.line; radius: 9 }
        contentItem: ColumnLayout {
            spacing: 5
            TextField {
                id: search; visible: root.searchable; Layout.fillWidth: true; implicitHeight: 34
                placeholderText: "搜索"; color: Theme.text; font.pixelSize: 13; selectByMouse: true
                background: Rectangle { color: Theme.bg; radius: 5; border.color: search.activeFocus?Theme.accent:Theme.line }
                onTextChanged: list.currentIndex=0
                Keys.onPressed: function(event){
                    if(event.key===Qt.Key_Tab){popup.close();event.accepted=false;return;}
                    if(event.key===Qt.Key_Down){list.currentIndex=Math.min(list.count-1,list.currentIndex+1);event.accepted=true;}
                    else if(event.key===Qt.Key_Up){list.currentIndex=Math.max(0,list.currentIndex-1);event.accepted=true;}
                    else if(event.key===Qt.Key_Return||event.key===Qt.Key_Enter){root.pick(list.currentIndex);event.accepted=true;}
                }
            }
            ListView {
                id: list; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                model: root.filtered(); boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                delegate: UiButton {
                    required property var modelData; required property int index
                    width: list.width; height: 35; quiet: true; selected: modelData.value===root.value
                    text: modelData.label; Accessible.name: text
                    onHoveredChanged: if(hovered)list.currentIndex=index
                    onClicked: root.pick(index)
                    background: Rectangle { radius: 5; color: parent.hovered||list.currentIndex===parent.index?Theme.selection:"transparent" }
                }
                Keys.onPressed: function(event){
                    if(event.key===Qt.Key_Tab){popup.close();event.accepted=false;return;}
                    if(event.key===Qt.Key_Return||event.key===Qt.Key_Enter||event.key===Qt.Key_Space){root.pick(currentIndex);event.accepted=true;}
                    else if(event.key===Qt.Key_Home){currentIndex=0;event.accepted=true;}
                    else if(event.key===Qt.Key_End){currentIndex=count-1;event.accepted=true;}
                }
            }
            Text { visible: list.count===0; text: "没有匹配项"; color: Theme.muted; font.pixelSize: 13; Layout.margins: 10 }
        }
        enter: Transition { enabled: Theme.motion; NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 100 } }
    }
}
