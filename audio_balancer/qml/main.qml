import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window

// Windows 11 (Fluent) look: Mica-like background, cards with a hairline border,
// 8 px corners, accent-colored controls, light/dark following the system.
// Light on resources: no shader effects, the meter timer only runs while visible.
ApplicationWindow {
    id: win
    visible: true
    width: 440
    minimumWidth: 400
    height: Math.min(780, backend.maxHeight)
    minimumHeight: 420
    title: backend.tr.title
    font.family: "Segoe UI Variable Text, Segoe UI"
    font.pixelSize: 14

    readonly property bool dark: Qt.styleHints.colorScheme === Qt.Dark
    readonly property color bg: dark ? "#202020" : "#f3f3f3"
    readonly property color card: dark ? "#2b2b2b" : "#fbfbfb"
    readonly property color stroke: dark ? "#383838" : "#e5e5e5"
    readonly property color ink: dark ? "#ffffff" : "#1b1b1b"
    readonly property color inkDim: dark ? "#c5c5c5" : "#5d5d5d"
    readonly property color hover: dark ? "#333333" : "#f0f0f0"
    readonly property color accent: dark ? "#60cdff" : "#0067c0"
    readonly property color talk: "#f7a928"
    readonly property string iconFont: backend.iconFont

    color: bg
    SystemPalette { id: sysPal }

    onClosing: (close) => { close.accepted = true; backend.windowClosing() }
    onVisibilityChanged: backend.active = visible && visibility !== Window.Minimized

    function appLabel(exe) {
        var n = exe.replace(".exe", "")
        return n.charAt(0).toUpperCase() + n.slice(1)
    }

    // ---------------------------------------------------------------- pieces
    component Card: Rectangle {
        radius: 8
        color: win.card
        border.width: 1
        border.color: win.stroke
    }

    component Caption: Text {
        color: win.inkDim
        font.pixelSize: 12
        font.weight: Font.DemiBold
    }

    component FluentSwitch: Switch {
        id: sw
        implicitWidth: 44; implicitHeight: 22
        padding: 0
        indicator: Rectangle {
            width: 40; height: 20; radius: 10
            anchors.verticalCenter: parent.verticalCenter
            color: sw.checked ? win.accent : "transparent"
            border.width: 1
            border.color: sw.checked ? win.accent : win.inkDim
            Rectangle {
                width: sw.pressed ? 17 : 12; height: 12; radius: 6
                anchors.verticalCenter: parent.verticalCenter
                x: sw.checked ? parent.width - width - 4 : 4
                color: sw.checked ? (win.dark ? "#1b1b1b" : "white") : win.inkDim
                Behavior on x { NumberAnimation { duration: 110 } }
            }
        }
    }

    component FluentSlider: Slider {
        id: sl
        implicitHeight: 28
        background: Item {
            x: sl.leftPadding
            y: sl.topPadding + sl.availableHeight / 2 - 2
            width: sl.availableWidth; height: 4
            Rectangle { anchors.fill: parent; radius: 2; color: win.dark ? "#9a9a9a" : "#8a8a8a"; opacity: 0.6 }
            Rectangle { width: sl.visualPosition * parent.width; height: parent.height; radius: 2; color: win.accent }
        }
        handle: Rectangle {
            x: sl.leftPadding + sl.visualPosition * (sl.availableWidth - width)
            y: sl.topPadding + sl.availableHeight / 2 - height / 2
            width: 20; height: 20; radius: 10
            color: win.dark ? "#454545" : "#ffffff"
            border.width: 1; border.color: win.dark ? "#5a5a5a" : "#d0d0d0"
            Rectangle {
                anchors.centerIn: parent
                width: sl.pressed ? 8 : 12; height: width; radius: width / 2
                color: win.accent
                Behavior on width { NumberAnimation { duration: 90 } }
            }
        }
    }

    component SliderRow: Item {
        id: sr
        property string title
        property string valueText
        property real from: 0
        property real to: 100
        property real value: 0
        signal moved(real v)
        Layout.fillWidth: true
        implicitHeight: 56
        Text { x: 0; y: 0; text: sr.title; color: win.ink }
        Text { anchors.right: parent.right; y: 0; text: sr.valueText; color: win.inkDim }
        FluentSlider {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            from: sr.from; to: sr.to; value: sr.value
            onMoved: sr.moved(value)
        }
    }

    component ToggleRow: Item {
        id: tr
        property string title
        property bool checked
        signal toggled(bool v)
        Layout.fillWidth: true
        implicitHeight: 40
        Text { anchors.verticalCenter: parent.verticalCenter; text: tr.title; color: win.ink }
        FluentSwitch {
            anchors { right: parent.right; verticalCenter: parent.verticalCenter }
            checked: tr.checked
            onToggled: tr.toggled(checked)
        }
    }

    component Divider: Rectangle { Layout.fillWidth: true; height: 1; color: win.stroke }

    // ---------------------------------------------------------------- content
    Flickable {
        id: scroller
        anchors.fill: parent
        contentWidth: width
        contentHeight: col.height + 32
        boundsBehavior: Flickable.StopAtBounds
        clip: true
        interactive: contentHeight > height
        ScrollBar.vertical: ScrollBar { }

        ColumnLayout {
            id: col
            x: 16; y: 16
            width: scroller.width - 32
            spacing: 12

            // ---- status + sound bars
            Card {
                Layout.fillWidth: true
                implicitHeight: 128
                Column {
                    x: 20; y: 16
                    spacing: 2
                    Text {
                        text: backend.kind === "off" ? backend.tr.status_off
                            : backend.kind === "talking" ? backend.tr.hero_talking
                            : backend.tr.hero_idle
                        color: backend.kind === "talking" ? win.talk : win.ink
                        font.pixelSize: 28; font.weight: Font.DemiBold
                    }
                    Text {
                        text: win.appLabel(backend.voiceApp) + "  •  "
                              + backend.musicCount + " " + backend.tr.hero_apps
                        color: win.inkDim; font.pixelSize: 13
                    }
                }
                // sound bars: scrolling history of the call's level
                Item {
                    id: meter
                    anchors { left: parent.left; right: parent.right; bottom: parent.bottom
                              leftMargin: 20; rightMargin: 20; bottomMargin: 14 }
                    height: 40
                    readonly property int n: 40
                    property var hist: []
                    Timer {
                        interval: 70; repeat: true
                        running: win.visible && backend.active
                        onTriggered: {
                            var h = meter.hist.slice(-(meter.n - 1))
                            h.push(backend.kind === "off" ? 0 : backend.level)
                            meter.hist = h
                        }
                    }
                    Row {
                        anchors.fill: parent
                        spacing: 3
                        Repeater {
                            model: meter.n
                            delegate: Item {
                                width: (meter.width - 3 * (meter.n - 1)) / meter.n
                                height: meter.height
                                readonly property real v: {
                                    var i = index - (meter.n - meter.hist.length)
                                    return i >= 0 ? meter.hist[i] : 0
                                }
                                Rectangle {
                                    width: parent.width
                                    height: Math.max(3, parent.v * parent.height)
                                    anchors.bottom: parent.bottom
                                    radius: width / 2
                                    color: backend.kind === "talking" ? win.talk : win.accent
                                    opacity: parent.v > 0.02 ? 1.0 : 0.35
                                }
                            }
                        }
                    }
                }
            }

            // ---- call app
            Caption { text: backend.tr.call_tile; Layout.leftMargin: 4; Layout.topMargin: 4 }
            Card {
                Layout.fillWidth: true
                implicitHeight: 60
                Image {
                    id: callIcon
                    x: 14; anchors.verticalCenter: parent.verticalCenter
                    width: 32; height: 32
                    sourceSize: Qt.size(64, 64); smooth: true
                    source: "image://appicon/" + backend.voiceApp + "?v=" + backend.iconVersion
                }
                Text {
                    anchors { left: callIcon.right; leftMargin: 12; verticalCenter: parent.verticalCenter }
                    text: win.appLabel(backend.voiceApp)
                    color: win.ink; font.weight: Font.Medium
                }
                Button {
                    id: changeBtn
                    anchors { right: parent.right; rightMargin: 14; verticalCenter: parent.verticalCenter }
                    text: backend.tr.pick_change
                    padding: 8; leftPadding: 16; rightPadding: 16
                    contentItem: Text { text: changeBtn.text; color: win.ink; horizontalAlignment: Text.AlignHCenter }
                    background: Rectangle {
                        radius: 4
                        color: changeBtn.down ? win.stroke : changeBtn.hovered ? win.hover : "transparent"
                        border.width: 1; border.color: win.stroke
                    }
                    onClicked: picker.open()
                }
            }

            // ---- music apps
            Caption { text: backend.tr.music_apps; Layout.leftMargin: 4; Layout.topMargin: 4 }
            Card {
                Layout.fillWidth: true
                implicitHeight: appsCol.height + 8
                Column {
                    id: appsCol
                    y: 4
                    width: parent.width
                    Text {
                        visible: backend.musicApps.length === 0
                        width: parent.width; padding: 16
                        wrapMode: Text.WordWrap
                        text: backend.tr.no_apps
                        color: win.inkDim
                    }
                    Repeater {
                        model: backend.musicApps
                        delegate: Rectangle {
                            width: appsCol.width; height: 44
                            color: rowMa.containsMouse ? win.hover : "transparent"
                            readonly property bool isPlaying: backend.playing.indexOf(modelData.name) >= 0
                            Image {
                                id: rowIcon
                                x: 14; anchors.verticalCenter: parent.verticalCenter
                                width: 28; height: 28
                                sourceSize: Qt.size(56, 56); smooth: true
                                source: "image://appicon/" + modelData.name + "?v=" + backend.iconVersion
                            }
                            Column {
                                anchors { left: rowIcon.right; leftMargin: 12; verticalCenter: parent.verticalCenter }
                                Text { text: win.appLabel(modelData.name); color: win.ink }
                                Text {
                                    visible: isPlaying
                                    text: backend.tr.playing
                                    color: win.accent; font.pixelSize: 11
                                }
                            }
                            FluentSwitch {
                                anchors { right: parent.right; rightMargin: 14; verticalCenter: parent.verticalCenter }
                                checked: modelData.selected
                                onToggled: backend.toggleMusic(modelData.name)
                            }
                            MouseArea {
                                id: rowMa
                                anchors { left: parent.left; right: parent.right; top: parent.top; bottom: parent.bottom; rightMargin: 64 }
                                hoverEnabled: true
                                onClicked: backend.toggleMusic(modelData.name)
                            }
                        }
                    }
                }
            }

            // ---- how much to lower
            Caption { text: backend.tr.section_levels; Layout.leftMargin: 4; Layout.topMargin: 4 }
            Card {
                Layout.fillWidth: true
                implicitHeight: lv.implicitHeight + 28
                ColumnLayout {
                    id: lv
                    x: 16; y: 14
                    width: parent.width - 32
                    spacing: 8
                    SliderRow {
                        title: backend.tr.duck_music
                        valueText: Math.round(backend.duckMusic) + "%"
                        value: backend.duckMusic
                        onMoved: (v) => backend.duckMusic = v
                    }
                    SliderRow {
                        title: backend.tr.duck_other
                        valueText: Math.round(backend.duckOther) + "%"
                        value: backend.duckOther
                        onMoved: (v) => backend.duckOther = v
                    }
                    SliderRow {
                        title: backend.tr.sensitivity
                        valueText: backend.sensitivity.toFixed(1)
                        from: 1; to: 10
                        value: backend.sensitivity
                        onMoved: (v) => backend.sensitivity = v
                    }
                }
            }

            // ---- general
            Caption { text: backend.tr.section_general; Layout.leftMargin: 4; Layout.topMargin: 4 }
            Card {
                Layout.fillWidth: true
                implicitHeight: gen.implicitHeight + 16
                ColumnLayout {
                    id: gen
                    x: 16; y: 8
                    width: parent.width - 32
                    spacing: 0
                    ToggleRow {
                        title: backend.tr.dock_power
                        checked: backend.enabled
                        onToggled: (v) => backend.enabled = v
                    }
                    Divider { }
                    ToggleRow {
                        title: backend.tr.autostart
                        checked: backend.autostart
                        onToggled: (v) => backend.autostart = v
                    }
                    Divider { }
                    ToggleRow {
                        title: backend.tr.minimized
                        checked: backend.startMinimized
                        onToggled: (v) => backend.startMinimized = v
                    }
                }
            }

            Button {
                id: quitBtn
                Layout.alignment: Qt.AlignRight
                text: backend.tr.dock_quit
                padding: 8; leftPadding: 22; rightPadding: 22
                contentItem: Text { text: quitBtn.text; color: win.ink; horizontalAlignment: Text.AlignHCenter }
                background: Rectangle {
                    radius: 4
                    color: quitBtn.down ? win.stroke : quitBtn.hovered ? win.hover : win.card
                    border.width: 1; border.color: win.stroke
                }
                onClicked: backend.quit()
            }
        }
    }

    // ---------------------------------------------------------------- call app picker
    Popup {
        id: picker
        modal: true
        dim: true
        anchors.centerIn: Overlay.overlay
        width: Math.min(380, win.width - 32)
        height: Math.min(460, win.height - 40)
        padding: 0
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.35) }
        background: Rectangle {
            radius: 8
            color: win.card
            border.width: 1; border.color: win.stroke
        }
        contentItem: ColumnLayout {
            spacing: 6
            Text {
                Layout.topMargin: 16; Layout.leftMargin: 18
                text: backend.tr.pick_title
                color: win.ink; font.pixelSize: 16; font.weight: Font.DemiBold
            }
            ListView {
                Layout.fillWidth: true; Layout.fillHeight: true
                Layout.leftMargin: 8; Layout.rightMargin: 8
                clip: true
                model: backend.voiceChoices
                boundsBehavior: Flickable.StopAtBounds
                delegate: Rectangle {
                    width: ListView.view.width; height: 44; radius: 6
                    color: rowMa2.containsMouse ? win.hover : "transparent"
                    Rectangle {      // Fluent selection pill
                        visible: modelData === backend.voiceApp
                        width: 3; height: 18; radius: 1.5; color: win.accent
                        anchors { left: parent.left; verticalCenter: parent.verticalCenter }
                    }
                    Row {
                        anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 14 }
                        spacing: 12
                        Image {
                            width: 26; height: 26
                            sourceSize: Qt.size(52, 52); smooth: true
                            source: "image://appicon/" + modelData + "?v=" + backend.iconVersion
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: win.appLabel(modelData)
                            color: win.ink
                        }
                    }
                    MouseArea {
                        id: rowMa2
                        anchors.fill: parent; hoverEnabled: true
                        onClicked: { backend.voiceApp = modelData; picker.close() }
                    }
                }
            }
            TextField {
                id: custom
                Layout.fillWidth: true
                Layout.leftMargin: 16; Layout.rightMargin: 16; Layout.bottomMargin: 16
                placeholderText: backend.tr.pick_custom
                placeholderTextColor: win.inkDim
                color: win.ink
                leftPadding: 12
                background: Rectangle {
                    radius: 4; color: win.bg
                    border.width: 1; border.color: custom.activeFocus ? win.accent : win.stroke
                }
                onAccepted: { backend.voiceApp = text; text = ""; picker.close() }
            }
        }
    }
}
