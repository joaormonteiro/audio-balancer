import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window

ApplicationWindow {
    id: win
    visible: !backend.startHidden
    width: 440
    height: Math.min(800, backend.maxHeight)
    minimumWidth: 400
    minimumHeight: 520
    color: "transparent"
    title: backend.tr.title
    font.family: "Segoe UI Variable Text, Segoe UI"
    font.pixelSize: 14

    readonly property color accent: backend.kind === "talking" ? "#ffc46b"
                                  : backend.kind === "off" ? "#9aa3b2" : "#62f0d4"
    readonly property color textMain: "#f4f7ff"
    readonly property color textDim: Qt.rgba(0.90, 0.94, 1, 0.78)

    onClosing: (close) => { close.accepted = false; win.hide() }

    Connections {
        target: backend
        function onShowRequested() { win.show(); win.raise(); win.requestActivate() }
    }

    // ---------------------------------------------------------------- reusable pieces
    component GlassCard: Rectangle {
        radius: 22
        color: Qt.rgba(1, 1, 1, 0.065)
        border.width: 1
        border.color: Qt.rgba(1, 1, 1, 0.18)
        Rectangle {          // soft sheen, brighter at the top like light on glass
            anchors.fill: parent
            anchors.margins: 1
            radius: parent.radius - 1
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, 0.13) }
                GradientStop { position: 0.45; color: Qt.rgba(1, 1, 1, 0.015) }
                GradientStop { position: 1.0; color: Qt.rgba(1, 1, 1, 0.045) }
            }
        }
        Rectangle {          // thin specular line along the top edge
            height: 1
            anchors { top: parent.top; left: parent.left; right: parent.right
                      leftMargin: parent.radius; rightMargin: parent.radius; topMargin: 1 }
            color: Qt.rgba(1, 1, 1, 0.38)
        }
    }

    component GlassSwitch: Switch {
        id: sw
        implicitWidth: 52
        implicitHeight: 30
        indicator: Rectangle {
            width: 52; height: 30; radius: 15
            x: sw.leftPadding; y: sw.topPadding + (sw.availableHeight - height) / 2
            color: sw.checked ? Qt.rgba(0.38, 0.94, 0.83, 0.85) : Qt.rgba(1, 1, 1, 0.16)
            border.width: 1
            border.color: sw.checked ? Qt.rgba(1, 1, 1, 0.55) : Qt.rgba(1, 1, 1, 0.28)
            Behavior on color { ColorAnimation { duration: 160 } }
            Rectangle {
                width: 24; height: 24; radius: 12
                y: 3
                x: sw.checked ? parent.width - width - 3 : 3
                color: "white"
                Behavior on x { NumberAnimation { duration: 170; easing.type: Easing.OutCubic } }
                Rectangle { anchors.fill: parent; radius: 12; z: -1; anchors.topMargin: 2
                            color: Qt.rgba(0, 0, 0, 0.30) }
            }
        }
        contentItem: Item {}
    }

    component GlassSlider: Slider {
        id: sl
        implicitHeight: 30
        background: Item {
            x: sl.leftPadding
            y: sl.topPadding + sl.availableHeight / 2 - 4
            width: sl.availableWidth
            height: 8
            Rectangle {
                anchors.fill: parent; radius: 4
                color: Qt.rgba(1, 1, 1, 0.13)
                border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.12)
            }
            Rectangle {
                width: Math.max(8, sl.visualPosition * parent.width)
                height: parent.height; radius: 4
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "#8a7dff" }
                    GradientStop { position: 1.0; color: "#62f0d4" }
                }
            }
        }
        handle: Item {
            x: sl.leftPadding + sl.visualPosition * (sl.availableWidth - width)
            y: sl.topPadding + sl.availableHeight / 2 - height / 2
            width: 26; height: 26
            Rectangle { anchors.fill: parent; anchors.topMargin: 3; radius: 13; color: Qt.rgba(0, 0, 0, 0.30) }
            Rectangle {
                anchors.fill: parent; radius: 13
                color: sl.pressed ? "#ffffff" : Qt.rgba(1, 1, 1, 0.92)
                border.width: 1; border.color: "white"
                scale: sl.pressed ? 1.08 : 1.0
                Behavior on scale { NumberAnimation { duration: 120 } }
            }
        }
    }

    component GlassCheck: CheckBox {
        id: cb
        implicitHeight: 32
        indicator: Rectangle {
            width: 22; height: 22; radius: 8
            x: cb.leftPadding; y: cb.topPadding + (cb.availableHeight - height) / 2
            color: cb.checked ? Qt.rgba(0.38, 0.94, 0.83, 0.85) : Qt.rgba(1, 1, 1, 0.12)
            border.width: 1
            border.color: cb.checked ? Qt.rgba(1, 1, 1, 0.6) : Qt.rgba(1, 1, 1, 0.3)
            Behavior on color { ColorAnimation { duration: 140 } }
            Text {
                anchors.centerIn: parent
                visible: cb.checked
                text: "✓"
                color: "#0b2a2a"
                font.pixelSize: 15; font.bold: true
            }
        }
        contentItem: Text {
            leftPadding: 32
            text: cb.text
            color: textMain
            font.pixelSize: 14
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
    }

    // ---------------------------------------------------------------- backdrop
    Rectangle {
        anchors.fill: parent
        color: backend.glass ? Qt.rgba(0.03, 0.04, 0.09, 0.52) : "#11141b"
    }
    Image {
        anchors.fill: parent
        source: backend.assets + "backdrop.png"
        fillMode: Image.PreserveAspectCrop
        opacity: backend.glass ? 0.7 : 1.0
        smooth: true
    }

    // ---------------------------------------------------------------- content
    Flickable {
        id: scroller
        anchors.fill: parent
        contentWidth: width
        contentHeight: col.implicitHeight + 30
        boundsBehavior: Flickable.StopAtBounds
        clip: true
        ScrollBar.vertical: ScrollBar {
            policy: scroller.contentHeight > scroller.height ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
            contentItem: Rectangle { implicitWidth: 4; radius: 2; color: Qt.rgba(1, 1, 1, 0.35) }
        }

        ColumnLayout {
            id: col
            x: 22; y: 14
            width: scroller.width - 44
            spacing: 10

            // ---- header
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                Image {
                    source: backend.assets + "icon.png"
                    sourceSize: Qt.size(96, 96)
                    Layout.preferredWidth: 46; Layout.preferredHeight: 46
                    smooth: true; mipmap: true
                }
                ColumnLayout {
                    spacing: 0
                    Text {
                        text: backend.tr.title
                        color: textMain
                        font.pixelSize: 23; font.weight: Font.DemiBold
                    }
                    Text {
                        Layout.fillWidth: true
                        text: backend.tr.subtitle
                        color: textDim; font.pixelSize: 12
                        wrapMode: Text.WordWrap
                    }
                }
            }

            // ---- status
            GlassCard {
                Layout.fillWidth: true
                implicitHeight: 90
                ColumnLayout {
                    anchors { fill: parent; margins: 16 }
                    spacing: 10
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        Item {
                            Layout.preferredWidth: 22; Layout.preferredHeight: 22
                            Rectangle {      // pulsing halo while someone talks
                                id: halo
                                anchors.centerIn: parent
                                width: 22; height: 22; radius: 11
                                color: accent; opacity: 0.0
                                SequentialAnimation on opacity {
                                    running: backend.kind === "talking"
                                    loops: Animation.Infinite
                                    NumberAnimation { to: 0.45; duration: 380 }
                                    NumberAnimation { to: 0.05; duration: 520 }
                                }
                            }
                            Rectangle {
                                anchors.centerIn: parent
                                width: 12; height: 12; radius: 6
                                color: accent
                                Behavior on color { ColorAnimation { duration: 200 } }
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            text: backend.kind === "off" ? backend.tr.status_off
                                : backend.kind === "talking" ? backend.tr.status_talking
                                : backend.tr.status_idle
                            color: textMain; font.pixelSize: 14; font.weight: Font.Medium
                            wrapMode: Text.WordWrap
                        }
                        GlassSwitch {
                            checked: backend.enabled
                            onToggled: backend.enabled = checked
                        }
                    }
                    // live level bars
                    Row {
                        id: bars
                        Layout.alignment: Qt.AlignHCenter
                        Layout.fillHeight: true
                        spacing: 4
                        Repeater {
                            id: rep
                            model: 34
                            delegate: Item {
                                property real j: 0.5
                                width: 6; height: bars.height
                                Rectangle {
                                    width: 6; radius: 3
                                    anchors.verticalCenter: parent.verticalCenter
                                    readonly property real prof: Math.sin(Math.PI * (index + 0.5) / 34)
                                    height: 5 + 38 * Math.min(1, backend.level)
                                              * (0.3 + 0.7 * prof) * (0.45 + 0.55 * parent.j)
                                    color: win.accent
                                    opacity: backend.kind === "off" ? 0.35 : 0.5 + 0.5 * Math.min(1, backend.level * 2)
                                    Behavior on height { NumberAnimation { duration: 90 } }
                                    Behavior on color { ColorAnimation { duration: 200 } }
                                }
                            }
                        }
                        Timer {
                            interval: 70; repeat: true
                            running: backend.level > 0.01 && win.visible
                            onTriggered: {
                                for (var i = 0; i < rep.count; ++i)
                                    rep.itemAt(i).j = Math.random()
                            }
                        }
                    }
                }
            }

            // ---- call app
            GlassCard {
                Layout.fillWidth: true
                implicitHeight: 84
                ColumnLayout {
                    anchors { fill: parent; margins: 16 }
                    spacing: 8
                    Text { text: backend.tr.voice_app; color: textMain; font.pixelSize: 13; font.weight: Font.DemiBold }
                    ComboBox {
                        id: combo
                        Layout.fillWidth: true
                        implicitHeight: 38
                        editable: true
                        model: backend.voiceChoices
                        Component.onCompleted: editText = backend.voiceApp
                        Connections {
                            target: backend
                            function onVoiceChanged() { if (!combo.activeFocus) combo.editText = backend.voiceApp }
                        }
                        onActivated: backend.voiceApp = currentText
                        onAccepted: backend.voiceApp = editText
                        background: Rectangle {
                            radius: 12
                            color: Qt.rgba(1, 1, 1, combo.activeFocus ? 0.16 : 0.10)
                            border.width: 1
                            border.color: Qt.rgba(1, 1, 1, combo.activeFocus ? 0.5 : 0.22)
                        }
                        contentItem: TextField {
                            leftPadding: 12; rightPadding: 36
                            text: combo.editText
                            onTextEdited: combo.editText = text
                            color: textMain
                            selectionColor: Qt.rgba(0.38, 0.94, 0.83, 0.5)
                            verticalAlignment: Text.AlignVCenter
                            font.pixelSize: 14
                            background: null
                        }
                        indicator: Text {
                            x: combo.width - width - 12
                            y: (combo.height - height) / 2
                            text: "⌄"
                            color: textDim; font.pixelSize: 18
                        }
                        delegate: ItemDelegate {
                            width: combo.width
                            height: 34
                            contentItem: Text {
                                text: modelData
                                color: textMain; font.pixelSize: 14
                                verticalAlignment: Text.AlignVCenter
                            }
                            background: Rectangle {
                                radius: 8
                                color: highlighted || hovered ? Qt.rgba(1, 1, 1, 0.14) : "transparent"
                            }
                            highlighted: combo.highlightedIndex === index
                        }
                        popup: Popup {
                            y: combo.height + 4
                            width: combo.width
                            implicitHeight: Math.min(contentItem.implicitHeight + 12, 220)
                            padding: 6
                            contentItem: ListView {
                                clip: true
                                implicitHeight: contentHeight
                                model: combo.popup.visible ? combo.delegateModel : null
                                currentIndex: combo.highlightedIndex
                            }
                            background: Rectangle {
                                radius: 14
                                color: Qt.rgba(0.10, 0.12, 0.20, 0.96)
                                border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.25)
                            }
                        }
                    }
                }
            }

            // ---- music apps
            GlassCard {
                Layout.fillWidth: true
                implicitHeight: 192
                ColumnLayout {
                    anchors { fill: parent; margins: 16 }
                    spacing: 4
                    Text { text: backend.tr.music_apps; color: textMain; font.pixelSize: 13; font.weight: Font.DemiBold }
                    Text {
                        Layout.fillWidth: true
                        text: backend.tr.music_hint
                        color: textDim; font.pixelSize: 11
                        wrapMode: Text.WordWrap
                    }
                    ListView {
                        id: list
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.topMargin: 4
                        clip: true
                        spacing: 0
                        model: backend.musicApps
                        boundsBehavior: Flickable.StopAtBounds
                        property real keepY: 0
                        onContentYChanged: if (!modelChanging) keepY = contentY
                        property bool modelChanging: false
                        onModelChanged: {
                            modelChanging = true
                            Qt.callLater(function () { list.contentY = list.keepY; list.modelChanging = false })
                        }
                        ScrollBar.vertical: ScrollBar {
                            contentItem: Rectangle { implicitWidth: 3; radius: 2; color: Qt.rgba(1, 1, 1, 0.3) }
                        }
                        delegate: RowLayout {
                            width: list.width - 8
                            height: 32
                            spacing: 6
                            GlassCheck {
                                Layout.fillWidth: true
                                text: modelData.name
                                checked: modelData.selected
                                onToggled: backend.setMusicApp(modelData.name, checked)
                            }
                            Text {    // little note marker while that app is making sound
                                visible: backend.playing.indexOf(modelData.name) >= 0
                                text: "♪"
                                color: win.accent; font.pixelSize: 15
                            }
                        }
                        Text {
                            anchors.centerIn: parent
                            visible: list.count === 0
                            text: backend.tr.no_apps
                            color: textDim; font.pixelSize: 12
                        }
                    }
                }
            }

            // ---- levels
            GlassCard {
                Layout.fillWidth: true
                implicitHeight: 182
                ColumnLayout {
                    anchors { fill: parent; margins: 16 }
                    spacing: 2
                    component SliderRow: ColumnLayout {
                        id: sr
                        property string label
                        property alias value: s.value
                        property real from: 0
                        property real to: 100
                        property bool percent: true
                        signal moved(real v)
                        Layout.fillWidth: true
                        spacing: 0
                        RowLayout {
                            Layout.fillWidth: true
                            Text { text: sr.label; color: textMain; font.pixelSize: 13; Layout.fillWidth: true }
                            Text {
                                text: sr.percent ? Math.round(s.value) + "%" : s.value.toFixed(1)
                                color: textMain; font.pixelSize: 13; font.weight: Font.DemiBold
                            }
                        }
                        GlassSlider {
                            id: s
                            Layout.fillWidth: true
                            from: sr.from; to: sr.to
                            onMoved: sr.moved(value)
                        }
                    }
                    SliderRow {
                        label: backend.tr.duck_music
                        value: backend.duckMusic
                        onMoved: (v) => backend.duckMusic = v
                    }
                    SliderRow {
                        label: backend.tr.duck_other
                        value: backend.duckOther
                        onMoved: (v) => backend.duckOther = v
                    }
                    SliderRow {
                        label: backend.tr.sensitivity
                        value: backend.sensitivity
                        from: 1; to: 10; percent: false
                        onMoved: (v) => backend.sensitivity = v
                    }
                }
            }

            // ---- startup toggles
            GlassCard {
                Layout.fillWidth: true
                implicitHeight: 90
                ColumnLayout {
                    anchors { fill: parent; margins: 16 }
                    spacing: 8
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: backend.tr.autostart; color: textMain; font.pixelSize: 14; Layout.fillWidth: true }
                        GlassSwitch { checked: backend.autostart; onToggled: backend.autostart = checked }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: backend.tr.minimized; color: textMain; font.pixelSize: 14; Layout.fillWidth: true }
                        GlassSwitch { checked: backend.startMinimized; onToggled: backend.startMinimized = checked }
                    }
                }
            }
        }
    }
}
