import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const OSD_TIMEOUT_MS = 900;
const OSD_FADE_MS = 350;

export default class VoiceToTextOsdExtension extends Extension {
    enable() {
        this._osd = null;
        this._osdTimeout = null;

        // Clean up OSD actors leaked by earlier crashed runs (e.g. an
        // exception between addChrome and the fade-out scheduling left
        // them stuck in the top-left corner).
        for (const actor of Main.uiGroup.get_children()) {
            if (actor.has_style_class_name?.('vtt-osd'))
                actor.destroy();
        }

        // The daemon emits via `gdbus emit`, whose sender is a unique bus
        // name (:1.x), so the sender filter must stay null; interface +
        // object path + member are sufficient discrimination.
        this._signalId = Gio.DBus.session.signal_subscribe(
            null,                              // sender (unique name varies)
            'dev.voice_to_text.Recorder',      // interface
            'StateChanged',                    // member
            '/dev/voice_to_text',              // object path
            null,                              // arg0
            Gio.DBusSignalFlags.NONE,
            (_conn, _sender, _path, _iface, _signal, params) => {
                const [state] = params.deep_unpack();
                this._showOsd(state === 'started');
            }
        );
    }

    disable() {
        if (this._signalId) {
            Gio.DBus.session.signal_unsubscribe(this._signalId);
            this._signalId = null;
        }
        this._destroyOsd();
    }

    _showOsd(started) {
        this._destroyOsd();

        const icon = new St.Icon({
            icon_name: started
                ? 'audio-input-microphone-symbolic'
                : 'media-playback-stop-symbolic',
            icon_size: 96,
            x_align: Clutter.ActorAlign.CENTER,
        });
        icon.add_style_class_name(started ? 'vtt-osd-icon-start' : 'vtt-osd-icon-stop');

        const label = new St.Label({
            text: started ? '开始录音' : '录音结束',
            x_align: Clutter.ActorAlign.CENTER,
        });
        label.add_style_class_name('vtt-osd-label');

        const box = new St.BoxLayout({
            vertical: true,
            style_class: 'vtt-osd',
            reactive: false,  // never capture clicks in the screen center
        });
        box.add_child(icon);
        box.add_child(label);

        // addChrome keeps the OSD above fullscreen windows. GNOME 47+
        // removed the affectsInputRegion param (input regions now derive
        // from reactive actors), so only affectsStruts is valid here.
        Main.layoutManager.addChrome(box, {affectsStruts: false});

        const monitor = Main.layoutManager.primaryMonitor;
        const [, width] = box.get_preferred_width(-1);
        const [, height] = box.get_preferred_height(-1);
        box.set_position(
            monitor.x + Math.round((monitor.width - width) / 2),
            monitor.y + Math.round((monitor.height - height) / 2)
        );

        box.set_pivot_point(0.5, 0.5);
        box.set_scale(0.85, 0.85);
        box.opacity = 0;
        box.ease({
            opacity: 255,
            scale_x: 1.0,
            scale_y: 1.0,
            duration: 180,
            mode: Clutter.AnimationMode.EASE_OUT_QUAD,
        });

        this._osd = box;
        this._osdTimeout = GLib.timeout_add(GLib.PRIORITY_DEFAULT, OSD_TIMEOUT_MS, () => {
            this._osdTimeout = null;
            if (this._osd) {
                this._osd.ease({
                    opacity: 0,
                    duration: OSD_FADE_MS,
                    mode: Clutter.AnimationMode.EASE_IN_QUAD,
                    onComplete: () => this._destroyOsd(),
                });
            }
            return GLib.SOURCE_REMOVE;
        });
    }

    _destroyOsd() {
        if (this._osdTimeout) {
            GLib.source_remove(this._osdTimeout);
            this._osdTimeout = null;
        }
        if (this._osd) {
            this._osd.remove_all_transitions();
            this._osd.destroy();
            this._osd = null;
        }
    }
}
