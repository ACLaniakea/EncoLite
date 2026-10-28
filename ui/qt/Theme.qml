pragma Singleton
import QtQuick
QtObject {
    function batteryLow(key) {
        var value = backend.state[key + '_value'];
        return !!value && value !== '—' && Number(backend.state[key + '_level']) <= 0.20;
    }
    function material(color, opacity, window) {
        return window && window.nativeGlass ? Qt.rgba(color.r,color.g,color.b,opacity) : color;
    }
    function surface(color, role, window) {
        var alpha = role === 'menu' ? (dark ? 0.76 : 0.70)
                  : role === 'selection' ? (dark ? 0.40 : 0.36)
                  : role === 'field' ? (dark ? 0.24 : 0.18)
                  : (dark ? 0.32 : 0.24);
        return material(color, alpha, window);
    }
    readonly property bool dark: backend ? !!backend.state.dark : false
    readonly property bool motion: backend ? backend.motion : false
    readonly property var palette: backend ? (backend.state.palette||{}) : ({})
    readonly property color bg: palette.bg||(dark ? "#151c18" : "#f5f8f6")
    readonly property color sidebar: palette.sidebar||(dark ? "#1a231e" : "#edf3ef")
    readonly property color card: palette.card||(dark ? "#202b24" : "#ffffff")
    readonly property color text: palette.text||(dark ? "#edf4ef" : "#24382b")
    readonly property color muted: palette.muted||(dark ? "#a4b7aa" : "#6b7f71")
    readonly property color line: palette.line||(dark ? "#34453a" : "#dce7df")
    readonly property color accent: palette.accent||(dark ? "#67d89a" : "#168b51")
    readonly property color selection: palette.selection||(dark ? "#2a4433" : "#e0f1e6")
    readonly property color accentText: palette.accent_text||(dark ? "#10291a" : "#ffffff")
    readonly property color error: dark ? "#ffaaa0" : "#bb473d"
}
