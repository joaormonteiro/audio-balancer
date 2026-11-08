import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Shapes
import QtQuick.Window

// Home-screen style UI: vivid wallpaper, frosted tiles, squircle icons, a dock.
// Kept deliberately light: no shader effects, no continuous animations, and
// updates only when a value actually changes (the backend ticks at 10 Hz).
ApplicationWindow {
    id: win
    visible: true
    width: 420
    minimumWidth: 420
    maximumWidth: 420
    height: Math.min(700, backend.maxHeight)
    minimumHeight: 420
    color: "#0b48e0"
    title: backend.tr.title
    font.family: "Segoe UI Variable Text, Segoe UI"

    readonly property string iconFont: backend.iconFont
    readonly property color accent: backend.kind === "talking" ? "#ffc44d"
                                  : backend.kind === "off" ? "#c4d2ee" : "#7dffd9"
    readonly property color ink: "#ffffff"
    readonly property color inkDim: Qt.rgba(1, 1, 1, 0.78)

    onClosing: (close) => { close.accepted = true; backend.windowClosing() }
    onVisibilityChanged: backend.active = visible && visibility !== Window.Minimized

    function appLabel(exe) {
        var n = exe.replace(".exe", "")
        return n.charAt(0).toUpperCase() + n.slice(1)
    }

    // ---------------------------------------------------------------- pieces
    component Tile: Rectangle {
        radius: 28
        color: Qt.rgba(1, 1, 1, 0.20)
        border.width: 1
        border.color: Qt.rgba(1, 1, 1, 0.40)
        Rectangle {          // light falling from the top, like frosted glass
            anchors.fill: parent
            anchors.margins: 1
            radius: parent.radius - 1
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, 0.20) }
                GradientStop { position: 1.0; color: Qt.rgba(1, 1, 1, 0.02) }
            }
        }
    }

    component Squircle: Rectangle {
        id: sq
        property string glyph: ""
        property color c1: "#ffffff"
        property color c2: "#cccccc"
        property real glyphScale: 0.50
        width: 40; height: 40
        radius: width * 0.30
        gradient: Gradient {
            GradientStop { position: 0.0; color: sq.c1 }
            GradientStop { position: 1.0; color: sq.c2 }
        }
        border.width: 1
        border.color: Qt.rgba(1, 1, 1, 0.45)
        Text {
            anchors.centerIn: parent
            text: sq.glyph
            font.family: win.iconFont
            font.pixelSize: sq.width * sq.glyphScale
            color: "white"
        }
    }

    component ThinSlider: Slider {
        id: sl
        implicitHeight: 24
        background: Item {
            x: sl.leftPadding
            y: sl.topPadding + sl.availableHeight / 2 - 3
            width: sl.availableWidth
            height: 6
            Rectangle { anchors.fill: parent; radius: 3; color: Qt.rgba(1, 1, 1, 0.30) }
            Rectangle { width: sl.visualPosition * parent.width; height: parent.height; radius: 3; color: "white" }
        }
        handle: Rectangle {
            x: sl.leftPadding + sl.visualPosition * (sl.availableWidth - width)
            y: sl.topPadding + sl.availableHeight / 2 - height / 2
            width: 20; height: 20; radius: 10
            color: "white"
            border.width: 1; border.color: Qt.rgba(0.05, 0.25, 0.8, 0.25)
            scale: sl.pressed ? 1.12 : 1.0
            Behavior on scale { NumberAnimation { duration: 100 } }
        }
    }

    component ControlTile: Tile {
        id: ct
        property string glyph
        property color c1
        property color c2
        property string title
        property string valueText
        property real from: 0
        property real to: 100
        property real value: 0
        property bool wide: false
        signal moved(real v)

        Squircle {
            id: ico
            x: 14; y: 14
            width: 36; height: 36
            glyph: ct.glyph; c1: ct.c1; c2: ct.c2
        }
        Text {
            anchors { left: ico.right; leftMargin: 10; verticalCenter: ico.verticalCenter }
            text: ct.title
            color: win.ink; font.pixelSize: 13; font.weight: Font.Medium
        }
        Text {
            anchors { right: parent.right; rightMargin: 18; top: parent.top; topMargin: ct.wide ? 14 : 52 }
            visible: ct.wide
            text: ct.valueText
            color: win.ink; font.pixelSize: 26; font.weight: Font.Light
        }
        Text {
            visible: !ct.wide
            x: 18; y: 46
            text: ct.valueText
            color: win.ink; font.pixelSize: 32; font.weight: Font.Light
        }
        ThinSlider {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom
                      leftMargin: 18; rightMargin: 18; bottomMargin: 10 }
            from: ct.from; to: ct.to; value: ct.value
            onMoved: ct.moved(value)
        }
    }

    component DockItem: Item {
        id: di
        property string glyph
        property string label
        property bool on: false
        property color c1: "#4be3b0"
        property color c2: "#16a77d"
        signal clicked()
        width: 78; height: 84
        scale: ma.pressed ? 0.93 : 1.0
        Behavior on scale { NumberAnimation { duration: 90 } }
        Column {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 6
            Squircle {
                anchors.horizontalCenter: parent.horizontalCenter
                width: 54; height: 54
                glyph: di.glyph
                c1: di.on ? di.c1 : Qt.rgba(1, 1, 1, 0.34)
                c2: di.on ? di.c2 : Qt.rgba(1, 1, 1, 0.16)
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: di.label
                color: win.ink; font.pixelSize: 11
            }
        }
        MouseArea { id: ma; anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: di.clicked() }
    }

    // ---------------------------------------------------------------- scene
    Image {
        anchors.fill: parent
        source: backend.assets + "wallpaper.jpg"
        fillMode: Image.PreserveAspectCrop
        sourceSize: Qt.size(840, 1500)
        smooth: true
        cache: false
    }

    Flickable {
        id: scroller
        anchors.fill: parent
        contentWidth: width
        contentHeight: col.height + 22
        boundsBehavior: Flickable.StopAtBounds
        clip: true
        interactive: contentHeight > height

        Column {
            id: col
            x: 20; y: 6
            width: 380
            spacing: 12

            // ---- hero (where the phone shows the clock)
            Item {
                width: parent.width; height: 112
                Column {
                    anchors { left: parent.left; verticalCenter: parent.verticalCenter }
                    spacing: 0
                    Text {
                        text: backend.kind === "off" ? backend.tr.status_off
                            : backend.kind === "talking" ? backend.tr.hero_talking
                            : backend.tr.hero_idle
                        color: win.ink
                        font.pixelSize: 54; font.weight: Font.Light
                    }
                    Row {
                        spacing: 8
                        Rectangle {
                            width: 10; height: 10; radius: 5; color: win.accent
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: win.appLabel(backend.voiceApp) + "   •   "
                                  + backend.musicCount + " " + backend.tr.hero_apps
                            color: win.inkDim; font.pixelSize: 15
                        }
                    }
                }
            }

            // ---- row 1: call ring + music folder
            Row {
                spacing: 14
                Tile {
                    id: callTile
                    width: 183; height: 183
                    Item {
                        id: ring
                        property real value: backend.level
                        Behavior on value { NumberAnimation { duration: 120 } }
                        anchors { horizontalCenter: parent.horizontalCenter; top: parent.top; topMargin: 16 }
                        width: 120; height: 120
                        Shape {
                            anchors.fill: parent
                            preferredRendererType: Shape.CurveRenderer
                            ShapePath {
                                strokeColor: Qt.rgba(1, 1, 1, 0.30); strokeWidth: 8
                                fillColor: "transparent"
                                PathAngleArc { centerX: 60; centerY: 60; radiusX: 54; radiusY: 54; startAngle: -90; sweepAngle: 359.9 }
                            }
                            ShapePath {
                                strokeColor: win.accent; strokeWidth: 8
                                fillColor: "transparent"; capStyle: ShapePath.RoundCap
                                PathAngleArc {
                                    centerX: 60; centerY: 60; radiusX: 54; radiusY: 54; startAngle: -90
                                    sweepAngle: Math.max(0.1, 359.9 * Math.min(1, ring.value * 1.4))
                                }
                            }
                        }
                        Image {
                            anchors.centerIn: parent
                            width: 58; height: 58
                            sourceSize: Qt.size(116, 116)
                            smooth: true
                            source: "image://appicon/" + backend.voiceApp + "?v=" + backend.iconVersion
                        }
                    }
                    Text {
                        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 12 }
                        text: backend.tr.call_tile + "  ›"
                        color: win.ink; font.pixelSize: 12; font.weight: Font.Medium
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: picker.open()
                    }
                }

                Tile {
                    id: folder
                    width: 183; height: 183
                    Flickable {
                        x: 14; y: 14
                        width: 155; height: 142
                        contentHeight: grid.height
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        interactive: contentHeight > height
                        Grid {
                            id: grid
                            columns: 3
                            spacing: 10
                            Repeater {
                                model: backend.musicApps
                                delegate: Item {
                                    width: 41; height: 41
                                    scale: iconMa.pressed ? 0.9 : 1.0
                                    Behavior on scale { NumberAnimation { duration: 90 } }
                                    Image {
                                        anchors.fill: parent
                                        anchors.margins: 1
                                        sourceSize: Qt.size(82, 82)
                                        smooth: true
                                        source: "image://appicon/" + modelData.name + "?v=" + backend.iconVersion
                                        opacity: modelData.selected ? 1.0 : 0.38
                                    }
                                    Rectangle {      // check badge on the apps marked as music
                                        visible: modelData.selected
                                        width: 16; height: 16; radius: 8
                                        anchors { right: parent.right; bottom: parent.bottom; rightMargin: -2; bottomMargin: -2 }
                                        color: "#22c98f"
                                        border.width: 1.5; border.color: "white"
                                        Text { anchors.centerIn: parent; text: "✓"; color: "white"; font.pixelSize: 10; font.bold: true }
                                    }
                                    Rectangle {      // marker: this app is making sound right now
                                        visible: backend.playing.indexOf(modelData.name) >= 0
                                        width: 8; height: 8; radius: 4; color: "#ffd24d"
                                        anchors { right: parent.right; top: parent.top }
                                    }
                                    MouseArea {
                                        id: iconMa
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: backend.toggleMusic(modelData.name)
                                    }
                                }
                            }
                        }
                        Text {
                            anchors.centerIn: parent
                            visible: backend.musicApps.length === 0
                            width: parent.width
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            text: backend.tr.no_apps
                            color: win.inkDim; font.pixelSize: 12
                        }
                    }
                    Text {
                        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 12 }
                        text: backend.tr.music_apps
                        color: win.ink; font.pixelSize: 12; font.weight: Font.Medium
                    }
                }
            }

            // ---- row 2: music / games ducking
            Row {
                spacing: 14
                ControlTile {
                    width: 183; height: 124
                    glyph: ""; c1: "#ffb457"; c2: "#ff7a2f"
                    title: backend.tr.tile_music
                    valueText: Math.round(backend.duckMusic) + "%"
                    value: backend.duckMusic
                    onMoved: (v) => backend.duckMusic = v
                }
                ControlTile {
                    width: 183; height: 124
                    glyph: ""; c1: "#c58bff"; c2: "#7a4dff"
                    title: backend.tr.tile_games
                    valueText: Math.round(backend.duckOther) + "%"
                    value: backend.duckOther
                    onMoved: (v) => backend.duckOther = v
                }
            }

            // ---- row 3: sensitivity
            ControlTile {
                width: 380; height: 92
                wide: true
                glyph: ""; c1: "#5fe0e6"; c2: "#1c9bd8"
                title: backend.tr.sensitivity
                valueText: backend.sensitivity.toFixed(1)
                from: 1; to: 10
                value: backend.sensitivity
                onMoved: (v) => backend.sensitivity = v
            }

            // ---- dock
            Tile {
                width: 380; height: 108
                radius: 38
                Row {
                    anchors.centerIn: parent
                    spacing: 6
                    DockItem {
                        glyph: ""; label: backend.tr.dock_power
                        on: backend.enabled
                        onClicked: backend.enabled = !backend.enabled
                    }
                    DockItem {
                        glyph: ""; label: backend.tr.dock_start
                        on: backend.autostart
                        c1: "#6aa6ff"; c2: "#2a62e8"
                        onClicked: backend.autostart = !backend.autostart
                    }
                    DockItem {
                        glyph: ""; label: backend.tr.dock_min
                        on: backend.startMinimized
                        c1: "#ffb457"; c2: "#ff7a2f"
                        onClicked: backend.startMinimized = !backend.startMinimized
                    }
                    DockItem {
                        glyph: ""; label: backend.tr.dock_quit
                        on: true
                        c1: "#ff7a7a"; c2: "#e0364f"
                        onClicked: backend.quit()
                    }
                }
            }
        }
    }

    // ---------------------------------------------------------------- call app picker
    Popup {
        id: picker
        modal: true
        dim: true
        anchors.centerIn: Overlay.overlay
        width: 340
        height: Math.min(440, win.height - 40)
        padding: 0
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0.05, 0.3, 0.45) }
        background: Rectangle {
            radius: 30
            color: Qt.rgba(0.07, 0.26, 0.82, 0.96)
            border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.4)
        }
        contentItem: ColumnLayout {
            spacing: 6
            Text {
                Layout.topMargin: 18; Layout.leftMargin: 22
                text: backend.tr.pick_title
                color: win.ink; font.pixelSize: 17; font.weight: Font.Medium
            }
            ListView {
                Layout.fillWidth: true; Layout.fillHeight: true
                Layout.leftMargin: 12; Layout.rightMargin: 12
                clip: true
                model: backend.voiceChoices
                boundsBehavior: Flickable.StopAtBounds
                delegate: Rectangle {
                    width: ListView.view.width; height: 48; radius: 16
                    color: modelData === backend.voiceApp ? Qt.rgba(1, 1, 1, 0.22)
                         : rowMa.containsMouse ? Qt.rgba(1, 1, 1, 0.12) : "transparent"
                    Row {
                        anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 10 }
                        spacing: 12
                        Image {
                            width: 32; height: 32
                            sourceSize: Qt.size(64, 64); smooth: true
                            source: "image://appicon/" + modelData + "?v=" + backend.iconVersion
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData
                            color: win.ink; font.pixelSize: 14
                        }
                    }
                    Text {
                        visible: modelData === backend.voiceApp
                        anchors { right: parent.right; rightMargin: 16; verticalCenter: parent.verticalCenter }
                        text: "✓"; color: "white"; font.pixelSize: 16; font.bold: true
                    }
                    MouseArea {
                        id: rowMa
                        anchors.fill: parent; hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: { backend.voiceApp = modelData; picker.close() }
                    }
                }
            }
            TextField {
                id: custom
                Layout.fillWidth: true
                Layout.leftMargin: 18; Layout.rightMargin: 18; Layout.bottomMargin: 18
                placeholderText: backend.tr.pick_custom
                placeholderTextColor: Qt.rgba(1, 1, 1, 0.55)
                color: "white"
                font.pixelSize: 14
                leftPadding: 14
                background: Rectangle { radius: 16; color: Qt.rgba(1, 1, 1, 0.16); border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.35) }
                onAccepted: { backend.voiceApp = text; text = ""; picker.close() }
            }
        }
    }
}
