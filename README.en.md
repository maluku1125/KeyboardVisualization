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

The chroma color is selectable (Green / Blue / Magenta / Cyan / Custom). **If your key icons contain green they'd be keyed out too — switch to magenta or blue.** "Custom…" opens the system color picker.

## Recording format v2

Recordings embed icons deduplicated by content hash (a skill image reused by several keys is stored once), carry metadata (game / job / server / character / note / preset / input mode) and a **signature**. The viewer shows "✓ Verified" for files produced directly by the app, or "⚠ Modified" when the JSON has been hand-edited. Older v1 recordings still open fine and are shown as unverified.

## Performance & Input Latency

"**Low-latency mode**" is on by default: key states are read by polling, with no system hooks installed — the program is completely outside the game's input path and **adds zero key latency**. The trade-off: taps shorter than one frame (~16 ms at 60 fps) may be missed. Turning it off switches to global hooks, which give the most precise timing (best for chart recording) but route every key event through this program before it reaches the game, potentially adding a few milliseconds under load. "FPS limit" (30–240) lowers CPU usage when reduced.

## Antivirus False Positives

This app hooks global key input, which looks like a keylogger to antivirus engines, so **false positives are common**. The usual symptom is the app closing itself after ~30 seconds, or an "access denied" error — that's the antivirus deleting the temp folder a one-file exe unpacks into.

Fixes (any one of these):

1. **Use the folder build** (`KeyVisualizer.zip` — extract it and run `KeyVisualizer.exe` inside). It doesn't unpack to a temp directory, so it is far less likely to be flagged.
2. Add an exclusion: Windows Security → Virus & threat protection → Manage settings → Exclusions. Check "Protection history" first to confirm it was quarantined.
3. Just run `key_visualizer.py` with Python instead of building an exe.

A permanent fix requires a code-signing certificate (a few hundred USD per year).

### Which build to download

| Build | Best for | Downside |
|---|---|---|
| `KeyVisualizer.zip` (folder) | **Recommended**, most users | Must be extracted first |
| `KeyVisualizer_single.exe` | Carrying on a USB stick | Most likely to trip antivirus, slower start |

`build_exe.bat` produces both in one run — upload both and let users pick.

## Notes

- Some anti-cheat systems may block global input hooks. Exclusive-fullscreen games cannot be overlaid — switch the game to borderless windowed mode.
- Manual edits to `config.json` require a restart (changes made in the settings UI apply live).
