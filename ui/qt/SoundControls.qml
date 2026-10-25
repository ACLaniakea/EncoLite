import QtQuick
import QtQuick.Layouts
import "."
import "Ui.js" as U
ColumnLayout {
    id: root
    property var detail: U.details(backend.state)
    property bool compact: false
    readonly property bool menuOpen: detailSelect.popupVisible||presetSelect.popupVisible
    spacing: 9
    SettingRow {
        visible: root.detail.visible; title: root.detail.title; controlWidth: root.compact?193:210
        Layout.fillWidth: true
        UiSelect { id:detailSelect;width: parent.width; accessibleName: root.detail.title; options: root.detail.options; value: root.detail.current; enabled: root.detail.enabled&&!backend.state.busy; onChosen: function(value){backend.action('change_noise',[value]);} }
    }
    SettingRow {
        visible: (backend.state.presets||[]).length>0; title: "耳机音效"; controlWidth: root.compact?193:210
        Layout.fillWidth: true
        UiSelect { id:presetSelect;width: parent.width; accessibleName: "耳机音效"; options: U.options(backend.state.presets); value: backend.state.preset; enabled: !!backend.state.can_equalizer&&!backend.state.busy; onChosen: function(value){backend.action('change_preset',[value]);} }
    }
}
