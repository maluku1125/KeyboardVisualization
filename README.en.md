# Key Visualizer — Real-time Key Input Overlay for Streaming

[繁體中文](README.md) | English

Pressed keys (including mouse buttons) scroll across a timeline as rounded squares — held keys stretch longer — with live KPS stats. Uses global input hooks, so keys are captured even while your game is in the foreground.

## Hotkeys

| Key | Function |
|---|---|
| F1 | Toggle scroll direction (right→left / left→right) |
| F2 | Reset stats |
| F3 | Open/close settings |
| F4 | Start/stop recording (red dot while recording) |
| F8 | Toggle click-through (global, transparent mode) |
| ESC | Close settings / quit |

## Settings (F3)

Three tabs; every change applies instantly and is saved to `config.json`:

- **General**: language (中/EN), lane count, background opacity, hold length display (off = fixed squares), mouse tracking, click-through, key lock (unknown keys are only added while settings are open), scroll direction & speed, auto record, window size, always on top, now-line, stats bar, chroma-key mode.
- **Keys**: the full keyboard in QWERTY physical order plus mouse buttons (scroll with wheel). Per key: **Icon** to pick a custom image, **✕** to clear it, **Disable** to hide the key, and **− / +** to pin it to a fixed lane ("Auto" = dynamic).
- **Presets**: save your current key setup (icons, fixed lanes, disabled keys, labels, colors, lane count) as named presets and switch with one click — handy for different games with different icon sets. Stored in `presets/`.

## Recording (F4) & Chart Viewer

- Press F4 to start/stop, or enable "Auto record" (records from launch, saves on exit). Recordings are saved to `recordings/rec_<timestamp>.json` and contain every key event plus lanes, colors, labels, and base64-embedded key icons — a single shareable file.
- **Viewer**: <https://maluku1125.github.io/KeyboardVisualization/> (this is `index.html`, a fully static page). Drag & drop a recording to see the entire chart: wheel zoom, drag pan, click to seek, playback (Space, 0.5×–4×), KPS graph and stats. Files are parsed locally in your browser — nothing is uploaded.

## Click-through (F8)

In transparent mode, press F8 and mouse clicks pass straight through the overlay to the game underneath; press F8 again to restore. Click-through is temporarily lifted while the settings panel is open.

## Transparent Background (Windows only)

"BG opacity" affects only the background — key blocks stay fully opaque. Below 100% the window becomes a borderless, always-on-top overlay you can place right over your game and move by left-click dragging; at 0% only the keys remain visible. Press F3 to open settings (the window needs focus — click a key block or the taskbar icon first). Window size is adjustable in settings.

## OBS

Plain window capture works. For a clean cutout, enable chroma-key mode and add a Color Key filter, or simply use the transparent overlay mode on top of your scene.

## Notes

- Some anti-cheat systems may block global input hooks. Exclusive-fullscreen games cannot be overlaid — switch the game to borderless windowed mode.
- Manual edits to `config.json` require a restart (changes made in the settings UI apply live).
