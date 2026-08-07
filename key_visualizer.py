# -*- coding: utf-8 -*-
"""
Key Visualizer — 實況用即時按鍵可視化
- 全域監聽按鍵 (pynput),遊戲在前景也能捕捉
- 按鍵以圓角方形沿時間軸滑動 (預設右→左,可切換)
- KPS / Max KPS / 總按鍵數統計
- F3 設定:一般參數 + 按鍵頁(整張鍵盤:自訂圖片、固定軌道、停用)
- 背景透明度只影響背景,按鍵保持不透明 (Windows 分層視窗)。
  透明模式下視窗無邊框、置頂,可用滑鼠左鍵拖曳移動。

視窗內快捷鍵:
  F1  切換滑動方向    F2  重置統計    F3  設定頁面    ESC 離開

執行:  python key_visualizer.py
示範:  python key_visualizer.py --demo   (自動模擬按鍵,不需 pynput)
"""

import json
import os
import random
import sys
import threading
import time
from collections import deque

# 打包成 exe (PyInstaller) 時,設定檔要放在 exe 旁邊而不是暫存目錄
if getattr(sys, "frozen", False):
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    import pygame
except ImportError:
    with open(os.path.join(SCRIPT_DIR, "error.log"), "w", encoding="utf-8") as f:
        f.write("缺少 pygame 套件,請執行:\n    pip install pygame pynput\n")
    print("缺少 pygame 套件,請執行:  pip install pygame pynput")
    input("按 Enter 離開...")
    sys.exit(1)

CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
IS_WIN = sys.platform == "win32"

DEFAULT_CONFIG = {
    "language": "zh",                # "zh" 繁體中文 / "en" English
    "active_preset": "",             # 目前套用的 preset 名稱(顯示用)
    "direction": "rtl",              # "rtl" 右到左 / "ltr" 左到右
    "window_width": 960,
    "window_height": 340,
    "background_color": "#0e0e16",
    "background_opacity": 1.0,       # 0.0~1.0 只影響背景,按鍵不透明 (僅 Windows;0=完全穿透)
    "chroma_key": False,             # True 時背景改用 chroma_color,方便 OBS 色度去背
    "chroma_color": "#00FF00",
    "scroll_speed": 220,             # 像素/秒
    "show_hold": True,               # True 長按拉長;False 每次按壓都是固定正方形
    "track_all_keys": True,          # True 監聽全部按鍵;False 只監聽 tracked_keys
    "tracked_keys": ["z", "x", "space", "left", "down", "up", "right"],
    "key_labels": {"space": "SPACE", "up": "↑", "down": "↓", "left": "←", "right": "→"},
    "key_icons": {},                 # 例如 {"z": "icons/z.png"} 圖片會取代文字標籤
    "key_colors": {},                # 例如 {"z": "#FF6B9D"}
    "fixed_lanes": {},               # 例如 {"space": 0} 指定按鍵固定在第 1 條軌道
    "disabled_keys": [],             # 停用的按鍵(不顯示、不計入統計)
    "palette": ["#4FC3F7", "#FF6B9D", "#FFD54F", "#81C784", "#BA68C8", "#FF8A65", "#4DB6AC", "#F06292"],
    "default_color": None,
    "max_lanes": 8,
    "track_mouse": True,             # 偵測滑鼠按鍵(左/右/中/側鍵)
    "low_latency": True,             # 低延遲模式:輪詢取代 hook,不影響遊戲輸入(僅 Windows)
    "fps_limit": 60,                 # 畫面更新率上限
    "click_through": False,          # 點擊穿透(僅透明模式,全域 F8 切換)
    "lock_keys": True,               # 鎖定:非設定頁面開啟時,不自動新增按鍵軌道
    "auto_record": False,            # 啟動就自動開始錄製(F4 也可隨時開始/停止)
    "always_on_top": False,          # 視窗總是在最頂層(透明模式下強制開啟)
    "show_now_line": True,           # 畫面前緣的白色現在線
    "show_stats": True,
    "font_name": "microsoftjhenghei,msyh,arial",
    "min_note_px": 18
}

# 按鍵頁顯示的完整鍵盤清單(QWERTY 實體排列順序)
ALL_KEYS = (
    ["esc"] + [f"f{i}" for i in range(1, 13)]
    + ["`"] + list("1234567890") + ["-", "=", "backspace"]
    + ["tab"] + list("qwertyuiop") + ["[", "]", "\\"]
    + ["caps_lock"] + list("asdfghjkl") + [";", "'", "enter"]
    + ["shift"] + list("zxcvbnm") + [",", ".", "/"]
    + ["ctrl", "alt", "space"]
    + ["up", "down", "left", "right"]
    + ["insert", "delete", "home", "end", "page_up", "page_down"]
    + ["m_left", "m_right", "m_middle", "m_x1", "m_x2"]   # 滑鼠按鍵
)

# 內建顯示名稱(config 的 key_labels 可覆蓋)
FALLBACK_LABELS = {
    "m_left": "M左", "m_right": "M右", "m_middle": "M中", "m_x1": "M4", "m_x2": "M5",
    "space": "SPACE", "up": "↑", "down": "↓", "left": "←", "right": "→",
}

# ── 介面文字(zh / en)──────────────────────────────────────
STR = {
    "caption": {"zh": "Key Visualizer  |  F1 方向  F2 重置  F3 設定  F4 錄製  ESC 離開",
                "en": "Key Visualizer  |  F1 Direction  F2 Reset  F3 Settings  F4 Record  ESC Quit"},
    "hint": {"zh": "F3 設定  F4 錄製  F8 穿透", "en": "F3 Settings  F4 Record  F8 Click-thru"},
    "hint_ct": {"zh": "F3 設定  F4 錄製  F8 穿透中", "en": "F3 Settings  F4 Record  F8 Thru: ON"},
    "settings": {"zh": "設定", "en": "Settings"},
    "tab_general": {"zh": "一般", "en": "General"},
    "tab_keys": {"zh": "按鍵", "en": "Keys"},
    "tab_presets": {"zh": "Preset", "en": "Presets"},
    "on": {"zh": "開", "en": "On"},
    "off": {"zh": "關", "en": "Off"},
    "icon_btn": {"zh": "圖片", "en": "Icon"},
    "disable": {"zh": "停用", "en": "Disable"},
    "disabled": {"zh": "已停用", "en": "Disabled"},
    "auto": {"zh": "自動", "en": "Auto"},
    "lane_n": {"zh": "軌道 {n}", "en": "Lane {n}"},
    "scroll": {"zh": "(滾輪捲動)", "en": "(scroll)"},
    "tip_general": {"zh": "點 − / + 或按鈕切換,改動立即儲存 (F3/ESC 關閉)",
                    "en": "Click −/+ or buttons; saves instantly (F3/ESC closes)"},
    "tip_keys": {"zh": "「圖片」選檔、✕ 清除、停用不顯示;右側 − / + 固定軌道",
                 "en": "Icon = set image, ✕ = clear, Disable = hide; −/+ = fixed lane"},
    "tip_presets": {"zh": "「套用」切換組合;「儲存」把目前按鍵設定覆寫進該 preset",
                    "en": "Apply = switch; Save = overwrite preset with current key settings"},
    "apply": {"zh": "套用", "en": "Apply"},
    "save": {"zh": "儲存", "en": "Save"},
    "delete": {"zh": "刪除", "en": "Del"},
    "new_preset": {"zh": "+ 新增", "en": "+ New"},
    "no_presets": {"zh": "還沒有 preset,按右上「+ 新增」把目前設定存成一組",
                   "en": "No presets yet. Click \"+ New\" to save current settings."},
    "active_mark": {"zh": "● 使用中", "en": "● active"},
    "preset_name_title": {"zh": "新增 Preset", "en": "New Preset"},
    "preset_name_prompt": {"zh": "輸入 preset 名稱:", "en": "Enter preset name:"},
}

# preset 儲存的欄位(其餘設定為全域共用)
PRESET_FIELDS = ["key_icons", "fixed_lanes", "disabled_keys", "key_labels", "key_colors", "max_lanes"]


def hex_to_rgb(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def save_config(cfg):
    """原子寫入:先寫暫存檔再替換,避免程式被強制關閉時 config 變空檔。"""
    try:
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, CONFIG_PATH)
    except Exception as e:
        print(f"[warn] config.json 儲存失敗: {e}")


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user = json.load(f)
            cfg.update(user)
        except Exception as e:
            print(f"[warn] config.json 讀取失敗,使用預設值: {e}")
    # 舊版設定遷移:transparent_background=true → 透明度 0
    if cfg.pop("transparent_background", False):
        cfg["background_opacity"] = 0.0
    save_config(cfg)
    return cfg


PRESETS_DIR = os.path.join(SCRIPT_DIR, "presets")


def list_presets():
    if not os.path.isdir(PRESETS_DIR):
        return []
    return sorted(os.path.splitext(f)[0] for f in os.listdir(PRESETS_DIR) if f.endswith(".json"))


def save_preset_file(cfg, name):
    os.makedirs(PRESETS_DIR, exist_ok=True)
    data = {k: cfg[k] for k in PRESET_FIELDS}
    tmp = os.path.join(PRESETS_DIR, name + ".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, os.path.join(PRESETS_DIR, name + ".json"))


def load_preset_file(name):
    with open(os.path.join(PRESETS_DIR, name + ".json"), "r", encoding="utf-8") as f:
        return json.load(f)


def ask_text(title, prompt):
    try:
        import tkinter as tk
        from tkinter import simpledialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        s = simpledialog.askstring(title, prompt, parent=root)
        root.destroy()
        s = (s or "").strip()
        return "".join(c for c in s if c not in '\\/:*?"<>|')[:40]
    except Exception as e:
        print(f"[warn] 無法開啟輸入對話框: {e}")
        return ""


def pick_image_file():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(
            title="選擇按鍵圖片",
            filetypes=[("圖片", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"), ("所有檔案", "*.*")])
        root.destroy()
        return path or None
    except Exception as e:
        print(f"[warn] 無法開啟檔案對話框: {e}")
        return None


class KeyState:
    """執行緒安全的按鍵事件儲存。"""

    def __init__(self):
        self.lock = threading.Lock()
        self.disabled = set()
        self.active = {}
        self.notes = deque()
        self.press_times = deque()
        self.total = 0
        self.max_kps = 0
        self.recording = False
        self.rec = []
        self.rec_start = None
        self.req_clickthrough = False   # 全域 F8 請求切換點擊穿透

    def press(self, key, now):
        with self.lock:
            if key in self.disabled or key in self.active:
                return
            note = {"key": key, "start": now, "end": None}
            self.active[key] = note
            self.press_times.append(now)
            self.total += 1
            if self.recording:
                self.rec.append(note)

    def start_record(self, now):
        with self.lock:
            self.recording = True
            self.rec = [n for n in self.active.values()]   # 按住中的鍵也算
            self.rec_start = now

    def stop_record(self):
        with self.lock:
            self.recording = False
            notes, t0 = self.rec, self.rec_start
            self.rec = []
            self.rec_start = None
            return notes, t0

    def release(self, key, now):
        with self.lock:
            note = self.active.pop(key, None)
            if note:
                note["end"] = now
                self.notes.append(note)

    def snapshot(self, now, history):
        with self.lock:
            while self.notes and (now - self.notes[0]["end"]) > history:
                self.notes.popleft()
            while self.press_times and (now - self.press_times[0]) > 1.0:
                self.press_times.popleft()
            kps = len(self.press_times)
            if kps > self.max_kps:
                self.max_kps = kps
            return (list(self.notes), dict(self.active), kps, self.max_kps,
                    self.total, list(self.active.keys()))

    def reset_stats(self):
        with self.lock:
            self.total = 0
            self.max_kps = 0
            self.press_times.clear()


def normalize_key(key):
    try:
        c = key.char
        if c is not None:
            o = ord(c)
            if 1 <= o <= 26:
                return chr(o + 96)
            return c.lower()
    except AttributeError:
        pass
    name = getattr(key, "name", None)
    if name:
        return name.replace("_l", "").replace("_r", "") if name.startswith(("ctrl", "shift", "alt", "cmd")) else name
    return str(key)


def start_listener(state):
    from pynput import keyboard

    def on_press(key):
        if key == keyboard.Key.f8:
            state.req_clickthrough = True
        state.press(normalize_key(key), time.time())

    def on_release(key):
        state.release(normalize_key(key), time.time())

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.daemon = True
    listener.start()
    return listener


def start_mouse_listener(state, cfg):
    from pynput import mouse

    def on_click(x, y, button, pressed):
        if not cfg["track_mouse"]:
            return
        name = "m_" + button.name
        if pressed:
            state.press(name, time.time())
        else:
            state.release(name, time.time())

    listener = mouse.Listener(on_click=on_click)
    listener.daemon = True
    listener.start()
    return listener


def start_demo(state):
    keys = ["z", "x", "space", "left", "down", "up", "right", "shift", "a", "s", "d"]

    def run():
        while True:
            k = random.choice(keys)
            now = time.time()
            state.press(k, now)
            hold = random.uniform(0.04, 0.5)
            threading.Timer(hold, state.release, args=(k, time.time() + hold)).start()
            time.sleep(random.uniform(0.05, 0.35))

    threading.Thread(target=run, daemon=True).start()


class LaneManager:
    """把按鍵分配到軌道。fixed_lanes 指定的按鍵永遠固定;其餘動態分配並回收。"""

    def __init__(self, cfg):
        self.track_all = cfg["track_all_keys"]
        self.fixed = {k: int(v) for k, v in cfg.get("fixed_lanes", {}).items()}
        self.lanes = {}
        self.last_used = {}
        if self.track_all:
            self.max_lanes = max(1, int(cfg["max_lanes"]))
        else:
            tracked = cfg["tracked_keys"]
            self.max_lanes = max(1, len(tracked))
            for i, k in enumerate(tracked):
                if k not in self.fixed:
                    self.lanes[k] = i

    def set_max_lanes(self, n):
        if not self.track_all:
            return
        n = max(1, int(n))
        self.max_lanes = n
        for k in [k for k, l in self.lanes.items() if l >= n]:
            del self.lanes[k]

    def set_fixed(self, key, lane):
        if lane is None:
            self.fixed.pop(key, None)
        else:
            self.fixed[key] = int(lane)
            self.lanes.pop(key, None)

    def allowed(self, key):
        return self.track_all or key in self.lanes or key in self.fixed

    def lane_of(self, key, now, visible_keys=()):
        self.last_used[key] = now
        if key in self.fixed:
            return self.fixed[key]
        if key in self.lanes:
            return self.lanes[key]
        if not self.track_all:
            return None
        reserved = set(self.fixed.values())
        used = set(self.lanes.values()) | reserved
        for i in range(self.max_lanes):
            if i not in used:
                self.lanes[key] = i
                return i
        if not self.lanes:
            return None
        idle = [k for k in self.lanes if k not in visible_keys]
        pool = idle if idle else list(self.lanes)
        victim = min(pool, key=lambda k: self.last_used.get(k, 0))
        lane = self.lanes.pop(victim)
        self.lanes[key] = lane
        return lane


# ── Windows 分層視窗(逐像素透明:背景半透明、按鍵不透明)──────────
if IS_WIN:
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.windll.user32
    _gdi32 = ctypes.windll.gdi32

    class _BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD)]

    class _BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", _BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

    class _BLENDFUNCTION(ctypes.Structure):
        _fields_ = [("BlendOp", ctypes.c_byte), ("BlendFlags", ctypes.c_byte),
                    ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_byte)]

    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x80000
    ULW_ALPHA = 2
    AC_SRC_ALPHA = 1
    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2
    SWP_NOMOVE, SWP_NOSIZE, SWP_NOACTIVATE = 0x2, 0x1, 0x10

    def win_get_hwnd():
        return pygame.display.get_wm_info()["window"]

    def win_set_layered(hwnd, on):
        style = _user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style = (style | WS_EX_LAYERED) if on else (style & ~WS_EX_LAYERED)
        _user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

    _user32.SetWindowPos.argtypes = [wintypes.HWND, ctypes.c_ssize_t,
                                     ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                     wintypes.UINT]
    _user32.SetWindowPos.restype = wintypes.BOOL

    def win_set_topmost(hwnd, on):
        _user32.SetWindowPos(hwnd, HWND_TOPMOST if on else HWND_NOTOPMOST,
                             0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    WS_EX_TRANSPARENT = 0x20

    def win_set_clickthrough(hwnd, on):
        style = _user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style = (style | WS_EX_TRANSPARENT) if on else (style & ~WS_EX_TRANSPARENT)
        _user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

    def win_cursor_pos():
        pt = wintypes.POINT()
        _user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def win_window_pos(hwnd):
        r = wintypes.RECT()
        _user32.GetWindowRect(hwnd, ctypes.byref(r))
        return r.left, r.top

    def win_move_window(hwnd, x, y):
        _user32.SetWindowPos(hwnd, 0, x, y, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE | 0x4)

    # 低延遲模式:GetAsyncKeyState 輪詢用的 VK 對照表
    VK_MAP = {}
    for i in range(26):
        VK_MAP[0x41 + i] = chr(ord("a") + i)
    for i in range(10):
        VK_MAP[0x30 + i] = str(i)
    for i in range(12):
        VK_MAP[0x70 + i] = f"f{i + 1}"
    VK_MAP.update({
        0x20: "space", 0x0D: "enter", 0x10: "shift", 0x11: "ctrl", 0x12: "alt",
        0x09: "tab", 0x1B: "esc", 0x08: "backspace", 0x14: "caps_lock",
        0x2D: "insert", 0x2E: "delete", 0x24: "home", 0x23: "end",
        0x21: "page_up", 0x22: "page_down",
        0x26: "up", 0x28: "down", 0x25: "left", 0x27: "right",
        0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".", 0xBF: "/",
        0xC0: "`", 0xDB: "[", 0xDC: "\\", 0xDD: "]", 0xDE: "'",
        0x01: "m_left", 0x02: "m_right", 0x04: "m_middle", 0x05: "m_x1", 0x06: "m_x2",
    })

    _GetAsyncKeyState = _user32.GetAsyncKeyState

    def win_layered_update(hwnd, surf):
        """把 SRCALPHA surface 推上分層視窗(premultiplied ARGB)。"""
        w, h = surf.get_size()
        pm = surf.premul_alpha()
        to_bytes = getattr(pygame.image, "tobytes", None) or pygame.image.tostring
        data = to_bytes(pm, "BGRA")

        hdc_screen = _user32.GetDC(0)
        hdc_mem = _gdi32.CreateCompatibleDC(hdc_screen)
        bmi = _BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bits = ctypes.c_void_p()
        hbmp = _gdi32.CreateDIBSection(hdc_screen, ctypes.byref(bmi), 0,
                                       ctypes.byref(bits), None, 0)
        if not hbmp:
            _gdi32.DeleteDC(hdc_mem)
            _user32.ReleaseDC(0, hdc_screen)
            return
        ctypes.memmove(bits, data, len(data))
        old = _gdi32.SelectObject(hdc_mem, hbmp)
        size = wintypes.SIZE(w, h)
        pt_src = wintypes.POINT(0, 0)
        blend = _BLENDFUNCTION(0, 0, 255, AC_SRC_ALPHA)
        _user32.UpdateLayeredWindow(hwnd, hdc_screen, None, ctypes.byref(size),
                                    hdc_mem, ctypes.byref(pt_src), 0,
                                    ctypes.byref(blend), ULW_ALPHA)
        _gdi32.SelectObject(hdc_mem, old)
        _gdi32.DeleteObject(hbmp)
        _gdi32.DeleteDC(hdc_mem)
        _user32.ReleaseDC(0, hdc_screen)


# ── 一般設定項目(label/names 皆為 zh/en 雙語)──────────────
SETTING_ITEMS = [
    {"id": "language", "label": {"zh": "語言 Language", "en": "Language 語言"}, "type": "choice",
     "choices": ["zh", "en"], "names": {"zh": {"zh": "繁體中文", "en": "繁體中文"},
                                        "en": {"zh": "English", "en": "English"}}},
    {"id": "max_lanes", "label": {"zh": "軌道數", "en": "Lanes"}, "type": "int", "min": 1, "max": 16, "step": 1},
    {"id": "background_opacity", "label": {"zh": "背景透明度 (0%=穿透)", "en": "BG opacity (0% = invisible)"},
     "type": "pct", "min": 0.0, "max": 1.0, "step": 0.05},
    {"id": "show_hold", "label": {"zh": "顯示按壓長度 (關=正方形)", "en": "Hold length (off = square)"}, "type": "bool"},
    {"id": "track_mouse", "label": {"zh": "偵測滑鼠按鍵", "en": "Track mouse buttons"}, "type": "bool"},
    {"id": "low_latency", "label": {"zh": "低延遲模式 (輪詢, 不影響遊戲輸入)", "en": "Low-latency mode (polling)"}, "type": "bool"},
    {"id": "fps_limit", "label": {"zh": "畫面更新率上限 (FPS)", "en": "FPS limit"}, "type": "int", "min": 30, "max": 240, "step": 30},
    {"id": "click_through", "label": {"zh": "點擊穿透 (透明模式, F8 切換)", "en": "Click-through (F8 toggles)"}, "type": "bool"},
    {"id": "lock_keys", "label": {"zh": "鎖定按鍵 (只在設定開啟時新增)", "en": "Lock keys (add only in settings)"}, "type": "bool"},
    {"id": "direction", "label": {"zh": "滑動方向", "en": "Scroll direction"}, "type": "choice",
     "choices": ["rtl", "ltr"], "names": {"rtl": {"zh": "右 → 左", "en": "Right → Left"},
                                          "ltr": {"zh": "左 → 右", "en": "Left → Right"}}},
    {"id": "scroll_speed", "label": {"zh": "滑動速度", "en": "Scroll speed"}, "type": "int", "min": 60, "max": 600, "step": 20},
    {"id": "auto_record", "label": {"zh": "自動錄製 (啟動即錄)", "en": "Auto record on launch"}, "type": "bool"},
    {"id": "window_width", "label": {"zh": "視窗寬度", "en": "Window width"}, "type": "int", "min": 320, "max": 3840, "step": 40},
    {"id": "window_height", "label": {"zh": "視窗高度", "en": "Window height"}, "type": "int", "min": 160, "max": 2160, "step": 20},
    {"id": "always_on_top", "label": {"zh": "總是在最頂層", "en": "Always on top"}, "type": "bool"},
    {"id": "show_now_line", "label": {"zh": "顯示現在線 (前緣白線)", "en": "Show now-line"}, "type": "bool"},
    {"id": "show_stats", "label": {"zh": "顯示統計列", "en": "Show stats bar"}, "type": "bool"},
    {"id": "chroma_key", "label": {"zh": "綠幕模式 (OBS 色度去背)", "en": "Chroma key mode (OBS)"}, "type": "bool"},
]


def cur_lang(cfg):
    return "en" if cfg.get("language") == "en" else "zh"


def tr(cfg, key):
    return STR[key][cur_lang(cfg)]


def save_recording(cfg, notes, t0, t1):
    """把錄到的 note 存成自包含 JSON(含 base64 icon),回傳檔案路徑。"""
    import base64
    fixed = {k: int(v) for k, v in cfg.get("fixed_lanes", {}).items()}
    events = []
    used = set()
    for n in sorted(notes, key=lambda n: n["start"]):
        key = n["key"]
        used.add(key)
        lane = fixed.get(key, n.get("lane"))
        end = n["end"] if n["end"] is not None else t1
        events.append({"k": key,
                       "s": max(0, int(round((n["start"] - t0) * 1000))),
                       "e": max(0, int(round((end - t0) * 1000))),
                       "l": int(lane) if lane is not None else 0})
    # 最大 KPS(1 秒滑動窗)
    times = [e["s"] for e in events]
    max_kps = 0
    j = 0
    for i, t in enumerate(times):
        while times[j] <= t - 1000:
            j += 1
        max_kps = max(max_kps, i - j + 1)
    # 內嵌用到的 icon
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp"}
    icons_b64 = {}
    for k in used:
        p = cfg["key_icons"].get(k)
        if not p:
            continue
        fp = p if os.path.isabs(p) else os.path.join(SCRIPT_DIR, p)
        try:
            with open(fp, "rb") as f:
                raw = f.read()
            m = mime.get(os.path.splitext(fp)[1].lower(), "image/png")
            icons_b64[k] = f"data:{m};base64," + base64.b64encode(raw).decode()
        except Exception as e:
            print(f"[warn] 錄製內嵌 icon 失敗 {p}: {e}")
    rec = {
        "version": 1,
        "app": "Key Visualizer",
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_ms": max(1, int(round((t1 - t0) * 1000))),
        "direction": cfg["direction"],
        "max_lanes": int(cfg["max_lanes"]),
        "palette": cfg["palette"],
        "default_color": cfg["default_color"],
        "key_colors": cfg["key_colors"],
        "key_labels": cfg["key_labels"],
        "fixed_lanes": fixed,
        "total": len(events),
        "max_kps": max_kps,
        "events": events,
        "icons": icons_b64,
    }
    d = os.path.join(SCRIPT_DIR, "recordings")
    os.makedirs(d, exist_ok=True)
    fn = os.path.join(d, time.strftime("rec_%Y%m%d_%H%M%S") + ".json")
    with open(fn, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False)
    print(f"[info] 錄製已儲存: {fn}")
    return fn


def value_text(cfg, item):
    v = cfg[item["id"]]
    t = item["type"]
    if t == "bool":
        return tr(cfg, "on") if v else tr(cfg, "off")
    if t == "pct":
        return f"{int(round(v * 100))}%"
    if t == "choice":
        return item["names"][v][cur_lang(cfg)]
    return str(v)


def change_value(cfg, item, delta):
    i = item["id"]
    t = item["type"]
    old = cfg[i]
    if t == "bool":
        cfg[i] = not old
    elif t == "choice":
        ch = item["choices"]
        cfg[i] = ch[(ch.index(old) + 1) % len(ch)]
    elif t == "pct":
        cfg[i] = round(max(item["min"], min(item["max"], old + delta * item["step"])), 2)
    else:
        cfg[i] = int(max(item["min"], min(item["max"], old + delta * item["step"])))
    return cfg[i] != old


def main():
    demo = "--demo" in sys.argv
    cfg = load_config()

    state = KeyState()
    state.disabled = set(cfg["disabled_keys"])
    hooks = []                     # pynput listener 物件

    def start_hooks():
        if hooks:
            return
        try:
            hooks.append(start_listener(state))
        except Exception as e:
            print(f"[error] 無法啟動全域鍵盤監聽: {e}")
        try:
            hooks.append(start_mouse_listener(state, cfg))
        except Exception as e:
            print(f"[warn] 無法啟動滑鼠監聽: {e}")

    def stop_hooks():
        for l in hooks:
            try:
                l.stop()
            except Exception:
                pass
        hooks.clear()

    def polling_mode():
        return IS_WIN and cfg["low_latency"] and not demo

    if demo:
        start_demo(state)
    elif not polling_mode():
        start_hooks()
        if not hooks:
            print("        可先用  python key_visualizer.py --demo  預覽效果")
            return

    exit_after = None          # 測試用 --exit-after N
    if "--exit-after" in sys.argv:
        try:
            exit_after = float(sys.argv[sys.argv.index("--exit-after") + 1])
        except (IndexError, ValueError):
            pass
    app_start = time.time()
    if cfg["auto_record"] or "--record" in sys.argv:
        state.start_record(app_start)

    pygame.init()
    W, H = int(cfg["window_width"]), int(cfg["window_height"])
    pygame.display.set_caption(tr(cfg, "caption"))
    clock = pygame.time.Clock()

    display = None
    hwnd = None
    layered = False
    ct_active = False          # 點擊穿透目前是否生效

    def setup_window(want_layered):
        nonlocal display, hwnd, layered, ct_active
        ct_active = False      # 視窗重建後樣式重置
        want_layered = want_layered and IS_WIN
        flags = pygame.NOFRAME if want_layered else pygame.RESIZABLE
        display = pygame.display.set_mode((W, H), flags)
        layered = want_layered
        if IS_WIN:
            hwnd = win_get_hwnd()
            win_set_layered(hwnd, layered)
            win_set_topmost(hwnd, layered or cfg["always_on_top"])
            # 移除 Windows 11 在無邊框視窗上畫的外框線與圓角
            try:
                dwm = ctypes.windll.dwmapi
                corner = ctypes.c_int(1 if layered else 0)   # 1 = DWMWCP_DONOTROUND
                dwm.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(corner), 4)
                border = ctypes.c_uint(0xFFFFFFFE if layered else 0xFFFFFFFF)  # NONE / DEFAULT
                dwm.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(border), 4)
            except Exception:
                pass

    setup_window(cfg["background_opacity"] < 0.999)

    def make_font(size, bold=False):
        """SysFont 在部分電腦會因字型登錄檔異常而炸掉,逐層 fallback。"""
        try:
            return pygame.font.SysFont(cfg["font_name"], size, bold=bold)
        except Exception as e:
            print(f"[warn] SysFont 失敗,改用字型檔: {e}")
        for p in (r"C:\Windows\Fonts\msjh.ttc", r"C:\Windows\Fonts\msjhbd.ttc",
                  r"C:\Windows\Fonts\mingliu.ttc", r"C:\Windows\Fonts\simsun.ttc",
                  r"C:\Windows\Fonts\arial.ttf"):
            if os.path.exists(p):
                try:
                    f = pygame.font.Font(p, size)
                    f.set_bold(bold)
                    return f
                except Exception:
                    pass
        f = pygame.font.Font(None, size)   # pygame 內建字型(無中文)
        f.set_bold(bold)
        return f

    font = make_font(16)
    font_big = make_font(22, bold=True)

    palette = [hex_to_rgb(c) for c in cfg["palette"]]
    key_colors = {k: hex_to_rgb(v) for k, v in cfg["key_colors"].items()}
    default_color = hex_to_rgb(cfg["default_color"]) if cfg["default_color"] else None

    icons = {}

    def load_icon(key, path):
        p = path if os.path.isabs(path) else os.path.join(SCRIPT_DIR, path)
        try:
            img = pygame.image.load(p).convert_alpha()
            br = img.get_bounding_rect(min_alpha=8)   # 裁掉四周透明邊距,讓大小一致
            if br.w > 0 and br.h > 0:
                img = img.subsurface(br).copy()
            icons[key] = img
            return True
        except Exception as e:
            print(f"[warn] icon 載入失敗 {path}: {e}")
            return False

    def fit_icon(img, tw, th):
        """等比縮放到 tw x th 內(縮圖用)。"""
        sc = min(tw / img.get_width(), th / img.get_height())
        return pygame.transform.smoothscale(
            img, (max(1, int(img.get_width() * sc)), max(1, int(img.get_height() * sc))))

    def cover_icon(img, tw, th, radius):
        """等比放大填滿整個 tw x th,超出部分裁切,並套用圓角。"""
        sc = max(tw / img.get_width(), th / img.get_height())
        big = pygame.transform.smoothscale(
            img, (max(tw, int(img.get_width() * sc + 0.5)), max(th, int(img.get_height() * sc + 0.5))))
        cx = (big.get_width() - tw) // 2
        cy = (big.get_height() - th) // 2
        crop = big.subsurface((cx, cy, tw, th)).copy()
        mask = pygame.Surface((tw, th), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, tw, th), border_radius=radius)
        crop.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        return crop

    for k, path in cfg["key_icons"].items():
        load_icon(k, path)

    lanes = LaneManager(cfg)
    min_px = int(cfg["min_note_px"])
    label_cache = {}
    icon_cache = {}
    thumb_cache = {}

    def current_bg():
        return hex_to_rgb(cfg["chroma_color"] if cfg["chroma_key"] else cfg["background_color"])

    bg = current_bg()

    def on_setting_changed(item_id):
        nonlocal bg
        if item_id == "max_lanes":
            lanes.set_max_lanes(cfg["max_lanes"])
        if item_id == "chroma_key":
            bg = current_bg()
        if item_id == "background_opacity":
            want = cfg["background_opacity"] < 0.999
            if want != layered:
                setup_window(want)
        if item_id == "always_on_top" and IS_WIN:
            win_set_topmost(hwnd, layered or cfg["always_on_top"])
        if item_id == "language":
            pygame.display.set_caption(tr(cfg, "caption"))
        if item_id == "low_latency" and not demo:
            if polling_mode():
                stop_hooks()
            else:
                start_hooks()
        if item_id in ("window_width", "window_height"):
            nonlocal W, H
            W, H = int(cfg["window_width"]), int(cfg["window_height"])
            setup_window(layered)
        save_config(cfg)

    def color_of(key, lane):
        if key in key_colors:
            return key_colors[key]
        if default_color:
            return default_color
        return palette[lane % len(palette)]

    def label_of(key):
        return cfg["key_labels"].get(key) or FALLBACK_LABELS.get(key) or key.upper()

    # ── 按鍵頁動作 ──
    def choose_icon(key):
        path = pick_image_file()
        if not path:
            return
        # 統一先裁邊、存成 png 到 icons/,之後每次啟動載入的都是同一張處理過的圖
        try:
            img = pygame.image.load(path).convert_alpha()
            br = img.get_bounding_rect(min_alpha=8)
            if br.w > 0 and br.h > 0:
                img = img.subsurface(br).copy()
            icons_dir = os.path.join(SCRIPT_DIR, "icons")
            os.makedirs(icons_dir, exist_ok=True)
            safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in key) or "key"
            # 檔名帶時間戳:不同 preset 換圖時不會互相覆蓋
            out_rel = os.path.join("icons", f"{safe}_{int(time.time())}.png")
            pygame.image.save(img, os.path.join(SCRIPT_DIR, out_rel))
            icons[key] = img
            cfg["key_icons"][key] = out_rel
            icon_cache.pop(key, None)
            thumb_cache.pop(key, None)
            save_config(cfg)
        except Exception as e:
            print(f"[warn] icon 處理失敗 {path}: {e}")

    def clear_icon(key):
        cfg["key_icons"].pop(key, None)
        icons.pop(key, None)
        icon_cache.pop(key, None)
        thumb_cache.pop(key, None)
        save_config(cfg)

    def shift_fixed_lane(key, delta):
        cur = cfg["fixed_lanes"].get(key, -1)
        new = max(-1, min(lanes.max_lanes - 1, cur + delta))
        if new == cur:
            return
        if new < 0:
            cfg["fixed_lanes"].pop(key, None)
            lanes.set_fixed(key, None)
        else:
            cfg["fixed_lanes"][key] = new
            lanes.set_fixed(key, new)
        save_config(cfg)

    def toggle_disable(key):
        dl = set(cfg["disabled_keys"])
        if key in dl:
            dl.remove(key)
        else:
            dl.add(key)
            state.release(key, time.time())
        cfg["disabled_keys"] = sorted(dl)
        state.disabled = dl
        save_config(cfg)

    # ── Preset 動作 ──
    def apply_preset(name):
        nonlocal lanes
        try:
            data = load_preset_file(name)
        except Exception as e:
            print(f"[warn] preset 載入失敗 {name}: {e}")
            return
        for k in PRESET_FIELDS:
            if k in data:
                cfg[k] = data[k]
        cfg["active_preset"] = name
        state.disabled = set(cfg["disabled_keys"])
        lanes = LaneManager(cfg)
        icons.clear()
        icon_cache.clear()
        thumb_cache.clear()
        label_cache.clear()
        key_colors.clear()
        key_colors.update({k: hex_to_rgb(v) for k, v in cfg["key_colors"].items()})
        for k, p in cfg["key_icons"].items():
            load_icon(k, p)
        save_config(cfg)

    def save_preset(name):
        try:
            save_preset_file(cfg, name)
            cfg["active_preset"] = name
            save_config(cfg)
        except Exception as e:
            print(f"[warn] preset 儲存失敗 {name}: {e}")

    def new_preset():
        name = ask_text(tr(cfg, "preset_name_title"), tr(cfg, "preset_name_prompt"))
        if name:
            save_preset(name)

    def delete_preset(name):
        try:
            os.remove(os.path.join(PRESETS_DIR, name + ".json"))
            if cfg["active_preset"] == name:
                cfg["active_preset"] = ""
                save_config(cfg)
        except Exception as e:
            print(f"[warn] preset 刪除失敗 {name}: {e}")

    settings_open = False
    settings_page = "general"
    key_scroll = 0
    hit_rects = []
    drag = None            # (cursor_x0, cursor_y0, win_x0, win_y0)

    all_keys_order = list(ALL_KEYS)
    frame_count = 0
    poll_prev = set()

    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.VIDEORESIZE and not layered:
                W, H = ev.w, ev.h
                cfg["window_width"], cfg["window_height"] = W, H
                save_config(cfg)
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    if settings_open:
                        settings_open = False
                    else:
                        running = False
                elif ev.key == pygame.K_F1:
                    cfg["direction"] = "ltr" if cfg["direction"] == "rtl" else "rtl"
                    save_config(cfg)
                elif ev.key == pygame.K_F2:
                    state.reset_stats()
                elif ev.key == pygame.K_F3:
                    settings_open = not settings_open
                elif ev.key == pygame.K_F4:
                    if state.recording:
                        notes, t0 = state.stop_record()
                        if notes:
                            save_recording(cfg, notes, t0, time.time())
                    else:
                        state.start_record(time.time())
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                clicked = False
                if settings_open:
                    for rect, cb in hit_rects:
                        if rect.collidepoint(ev.pos):
                            cb()
                            clicked = True
                            break
                if not clicked and layered and not settings_open and IS_WIN:
                    cx, cy = win_cursor_pos()
                    wx, wy = win_window_pos(hwnd)
                    drag = (cx, cy, wx, wy)
            elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                drag = None
            elif ev.type == pygame.MOUSEWHEEL and settings_open:
                key_scroll = max(0, key_scroll - ev.y)

        if drag and IS_WIN:
            if pygame.mouse.get_pressed()[0]:
                cx, cy = win_cursor_pos()
                win_move_window(hwnd, drag[2] + cx - drag[0], drag[3] + cy - drag[1])
            else:
                drag = None

        # 全域 F8:切換點擊穿透
        if state.req_clickthrough:
            state.req_clickthrough = False
            if layered:
                cfg["click_through"] = not cfg["click_through"]
                save_config(cfg)
        # 套用點擊穿透(設定頁開啟時暫時關閉,才能操作介面)
        if IS_WIN:
            want_ct = layered and cfg["click_through"] and not settings_open
            if want_ct != ct_active:
                win_set_clickthrough(hwnd, want_ct)
                ct_active = want_ct

        now = time.time()

        # ── 低延遲模式:輪詢按鍵狀態(不掛 hook,零輸入延遲)──
        if polling_mode():
            pressed_now = set()
            mouse_off = not cfg["track_mouse"]
            for vk, name in VK_MAP.items():
                if mouse_off and vk <= 0x06:
                    continue
                if _GetAsyncKeyState(vk) & 0x8000:
                    pressed_now.add(name)
            for name in pressed_now - poll_prev:
                if name == "f8":
                    state.req_clickthrough = True
                state.press(name, now)
            for name in poll_prev - pressed_now:
                state.release(name, now)
            poll_prev = pressed_now
        elif poll_prev:
            for name in poll_prev:
                state.release(name, now)
            poll_prev = set()

        top = 46 if cfg["show_stats"] else 8
        lane_area = H - top - 8
        lane_h = lane_area / lanes.max_lanes
        note_h = max(10, int(lane_h * 0.72))
        speed = float(cfg["scroll_speed"])
        history = W / speed + 2.0
        direction = cfg["direction"]

        done, active, kps, max_kps, total, held = state.snapshot(now, history)

        # ── 繪圖目標:透明模式畫在 SRCALPHA surface,否則直接畫視窗 ──
        if layered:
            screen = pygame.Surface((W, H), pygame.SRCALPHA)
            if settings_open:
                bg_a = 238                     # 設定時背景加深方便閱讀
            else:
                bg_a = max(3, int(cfg["background_opacity"] * 255))  # 保留少量 alpha 才能點到視窗
            screen.fill((bg[0], bg[1], bg[2], bg_a))
        else:
            screen = display
            screen.fill(bg)

        # ── 統計列 ──
        stats_w = 0
        if cfg["show_stats"]:
            stats = f"KPS {kps:>2}   MAX {max_kps:>2}   TOTAL {total}"
            stats_surf = font_big.render(stats, True, (240, 240, 245))
            screen.blit(stats_surf, (12, 10))
            stats_w = 12 + stats_surf.get_width()
            hint_key = "hint_ct" if (ct_active or (layered and cfg["click_through"])) else "hint"
            hint = font.render(tr(cfg, hint_key), True, (150, 150, 170))
            screen.blit(hint, (W - hint.get_width() - 12, 4))
        if state.recording:
            rec_y = 20 if cfg["show_stats"] else 14
            rx = (stats_w + 30) if cfg["show_stats"] else 14
            pygame.draw.circle(screen, (255, 70, 70), (rx, rec_y), 6)
            el = int(now - (state.rec_start or now))
            rec_s = font.render(f"REC {el // 60:02d}:{el % 60:02d}", True, (255, 120, 120))
            screen.blit(rec_s, (rx + 12, rec_y - rec_s.get_height() // 2))
        if cfg["show_stats"]:
            if held:
                held_txt = "  ".join(label_of(k) for k in held[:10])
                surf = font.render(held_txt, True, (150, 220, 255))
                screen.blit(surf, (W - surf.get_width() - 12, 24))
            pygame.draw.line(screen, (70, 70, 90), (0, top - 4), (W, top - 4), 1)

        # ── 時間刻度 ──
        if not cfg["chroma_key"] and not layered:
            for s in range(int(history) + 1):
                off = (now % 1.0 + s) * speed
                x = W - off if direction == "rtl" else off
                if 0 <= x <= W:
                    pygame.draw.line(screen, (40, 40, 55), (int(x), top), (int(x), H - 6), 1)

        def time_to_x(t):
            off = (now - t) * speed
            return W - off if direction == "rtl" else off

        # ── 繪製 note ──
        all_notes = done + list(active.values())
        visible_keys = {n["key"] for n in all_notes}
        for note in all_notes:
            key = note["key"]
            if key in state.disabled or not lanes.allowed(key):
                continue
            # 鎖定模式:設定頁沒開時,不為陌生按鍵新增軌道
            if (cfg["lock_keys"] and not settings_open
                    and key not in lanes.fixed and key not in lanes.lanes
                    and note.get("lane") is None):
                continue
            if key in lanes.fixed:
                lane = lanes.fixed[key]
                lanes.last_used[key] = note["start"]
            else:
                lane = note.get("lane")
                if lane is None:
                    lane = lanes.lane_of(key, note["start"], visible_keys)
                    note["lane"] = lane
            if lane is None or lane >= lanes.max_lanes:
                continue
            y = top + lane * lane_h + (lane_h - note_h) / 2
            col = color_of(key, lane)
            radius = min(10, note_h // 2)

            if cfg["show_hold"]:
                end_t = note["end"] if note["end"] is not None else now
                xa, xb = time_to_x(note["start"]), time_to_x(end_t)
                x0, x1 = min(xa, xb), max(xa, xb)
                wpx = max(min_px, x1 - x0)
                if direction == "rtl":
                    x0 = x1 - wpx
            else:
                wpx = note_h
                x0 = time_to_x(note["start"]) - wpx / 2
                radius = min(8, note_h // 3)

            if x0 > W or x0 + wpx < 0:
                continue
            r = pygame.Rect(int(x0), int(y), int(wpx), note_h)
            if note["end"] is None:
                glow = pygame.Rect(r.x - 2, r.y - 2, r.w + 4, r.h + 4)
                pygame.draw.rect(screen, tuple(min(255, c + 70) for c in col), glow, border_radius=radius + 2)
            pygame.draw.rect(screen, col, r, border_radius=radius)

            if key in icons:
                cached = icon_cache.get(key)
                if cached is None or cached[0] != note_h:   # 尺寸變了就重建
                    icon_cache[key] = (note_h, cover_icon(icons[key], note_h, note_h, radius))
                img = icon_cache[key][1]
                if cfg["show_hold"]:
                    ix = r.right - img.get_width() if direction == "rtl" else r.x
                else:
                    ix = r.x
                screen.blit(img, (ix, r.y))
            else:
                if key not in label_cache:
                    label_cache[key] = font.render(label_of(key), True, (15, 15, 20))
                surf = label_cache[key]
                if surf.get_width() <= r.w - 4:
                    if cfg["show_hold"]:
                        lx = r.right - surf.get_width() - 5 if direction == "rtl" else r.x + 5
                    else:
                        lx = r.centerx - surf.get_width() // 2
                    screen.blit(surf, (lx, r.centery - surf.get_height() // 2))

        # ── 現在線 ──
        if cfg["show_now_line"]:
            edge_x = W - 1 if direction == "rtl" else 1
            pygame.draw.line(screen, (255, 255, 255), (edge_x, top), (edge_x, H - 6), 2)

        # ── 設定頁面 ──
        hit_rects = []
        if settings_open:
            lang = cur_lang(cfg)
            pw = 560
            row_h = 38
            visible_rows = max(3, (H - 120) // row_h)
            known_keys = all_keys_order + sorted(
                (set(cfg["key_icons"]) | set(cfg["fixed_lanes"]) | set(cfg["disabled_keys"])
                 | set(lanes.last_used)) - set(all_keys_order))
            presets = list_presets()
            if settings_page == "general":
                page_items = SETTING_ITEMS
            elif settings_page == "keys":
                page_items = known_keys
            else:
                page_items = presets
            n_rows = min(visible_rows, max(1, len(page_items)))
            ph = row_h * n_rows + 96
            px, py = (W - pw) // 2, max(8, (H - ph) // 2)
            panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
            panel.fill((18, 18, 28, 245))
            screen.blit(panel, (px, py))
            pygame.draw.rect(screen, (90, 90, 120), (px, py, pw, ph), 1, border_radius=8)

            def switch_page(t):
                nonlocal settings_page, key_scroll
                settings_page = t
                key_scroll = 0

            tabs = [("general", tr(cfg, "tab_general")), ("keys", tr(cfg, "tab_keys")),
                    ("presets", tr(cfg, "tab_presets"))]
            tx = px + 16
            for tid, tname in tabs:
                sel = settings_page == tid
                tsurf = font_big.render(tname, True, (240, 240, 245) if sel else (120, 120, 140))
                trect = pygame.Rect(tx, py + 10, tsurf.get_width() + 20, 30)
                if sel:
                    pygame.draw.rect(screen, (50, 50, 75), trect, border_radius=6)
                screen.blit(tsurf, (trect.x + 10, trect.y + 2))
                hit_rects.append((trect, (lambda t=tid: switch_page(t))))
                tx = trect.right + 8

            body_y = py + 50

            if settings_page == "general":
                max_scroll_g = max(0, len(SETTING_ITEMS) - visible_rows)
                key_scroll = min(key_scroll, max_scroll_g)
                shown_items = SETTING_ITEMS[key_scroll:key_scroll + visible_rows]
                if max_scroll_g > 0:
                    sc_txt = font.render(f"{key_scroll + 1}-{key_scroll + len(shown_items)} / {len(SETTING_ITEMS)}  {tr(cfg, 'scroll')}",
                                         True, (140, 140, 160))
                    screen.blit(sc_txt, (px + pw - sc_txt.get_width() - 16, py + 16))
                for idx, item in enumerate(shown_items):
                    ry = body_y + idx * row_h
                    screen.blit(font.render(item["label"][lang], True, (210, 210, 220)), (px + 16, ry + 8))
                    val = font.render(value_text(cfg, item), True, (150, 220, 255))
                    if item["type"] in ("int", "pct"):
                        plus = pygame.Rect(px + pw - 44, ry + 4, 28, 26)
                        minus = pygame.Rect(px + pw - 148, ry + 4, 28, 26)
                        for rect, sign in ((minus, "−"), (plus, "+")):
                            pygame.draw.rect(screen, (55, 55, 75), rect, border_radius=6)
                            s = font_big.render(sign, True, (230, 230, 240))
                            screen.blit(s, (rect.centerx - s.get_width() // 2,
                                            rect.centery - s.get_height() // 2))
                        screen.blit(val, ((minus.right + plus.left - val.get_width()) // 2, ry + 8))
                        hit_rects.append((minus, (lambda it=item: (change_value(cfg, it, -1)
                                                                   and on_setting_changed(it["id"])))))
                        hit_rects.append((plus, (lambda it=item: (change_value(cfg, it, +1)
                                                                  and on_setting_changed(it["id"])))))
                    else:
                        btn = pygame.Rect(px + pw - 148, ry + 4, 132, 26)
                        pygame.draw.rect(screen, (55, 55, 75), btn, border_radius=6)
                        screen.blit(val, (btn.centerx - val.get_width() // 2, ry + 8))
                        hit_rects.append((btn, (lambda it=item: (change_value(cfg, it, +1)
                                                                 and on_setting_changed(it["id"])))))
                tip = font.render(tr(cfg, "tip_general"), True, (140, 140, 160))
            elif settings_page == "keys":
                max_scroll = max(0, len(known_keys) - visible_rows)
                key_scroll = min(key_scroll, max_scroll)
                shown = known_keys[key_scroll:key_scroll + visible_rows]
                for idx, key in enumerate(shown):
                    ry = body_y + idx * row_h
                    disabled = key in state.disabled
                    name_col = (110, 110, 125) if disabled else (210, 210, 220)
                    screen.blit(font.render(label_of(key), True, name_col), (px + 16, ry + 8))
                    # icon 縮圖
                    if key in icons:
                        if key not in thumb_cache:
                            thumb_cache[key] = fit_icon(icons[key], 24, 24)
                        screen.blit(thumb_cache[key], (px + 118, ry + 5))
                    # 圖片
                    pic_btn = pygame.Rect(px + 160, ry + 4, 52, 26)
                    pygame.draw.rect(screen, (55, 55, 75), pic_btn, border_radius=6)
                    s = font.render(tr(cfg, "icon_btn"), True, (230, 230, 240))
                    screen.blit(s, (pic_btn.centerx - s.get_width() // 2, ry + 8))
                    hit_rects.append((pic_btn, (lambda k=key: choose_icon(k))))
                    # 清除圖片
                    if key in cfg["key_icons"]:
                        clr_btn = pygame.Rect(pic_btn.right + 6, ry + 4, 30, 26)
                        pygame.draw.rect(screen, (80, 45, 50), clr_btn, border_radius=6)
                        s = font.render("✕", True, (240, 190, 190))
                        screen.blit(s, (clr_btn.centerx - s.get_width() // 2, ry + 8))
                        hit_rects.append((clr_btn, (lambda k=key: clear_icon(k))))
                    # 停用 / 啟用
                    dis_btn = pygame.Rect(px + 268, ry + 4, 64, 26)
                    pygame.draw.rect(screen, (90, 50, 55) if disabled else (55, 55, 75),
                                     dis_btn, border_radius=6)
                    s = font.render(tr(cfg, "disabled") if disabled else tr(cfg, "disable"), True,
                                    (255, 170, 170) if disabled else (230, 230, 240))
                    screen.blit(s, (dis_btn.centerx - s.get_width() // 2, ry + 8))
                    hit_rects.append((dis_btn, (lambda k=key: toggle_disable(k))))
                    # 固定軌道 − 值 +
                    plus = pygame.Rect(px + pw - 44, ry + 4, 28, 26)
                    minus = pygame.Rect(px + pw - 170, ry + 4, 28, 26)
                    for rect, sign in ((minus, "−"), (plus, "+")):
                        pygame.draw.rect(screen, (55, 55, 75), rect, border_radius=6)
                        s2 = font_big.render(sign, True, (230, 230, 240))
                        screen.blit(s2, (rect.centerx - s2.get_width() // 2,
                                         rect.centery - s2.get_height() // 2))
                    fl = cfg["fixed_lanes"].get(key)
                    vtxt = tr(cfg, "auto") if fl is None else tr(cfg, "lane_n").format(n=fl + 1)
                    vs = font.render(vtxt, True, (150, 220, 255) if fl is None else (255, 214, 120))
                    screen.blit(vs, ((minus.right + plus.left - vs.get_width()) // 2, ry + 8))
                    hit_rects.append((minus, (lambda k=key: shift_fixed_lane(k, -1))))
                    hit_rects.append((plus, (lambda k=key: shift_fixed_lane(k, +1))))
                sc_txt = font.render(f"{key_scroll + 1}-{key_scroll + len(shown)} / {len(known_keys)}  {tr(cfg, 'scroll')}",
                                     True, (140, 140, 160))
                screen.blit(sc_txt, (px + pw - sc_txt.get_width() - 16, py + 16))
                tip = font.render(tr(cfg, "tip_keys"), True, (140, 140, 160))
            else:
                # ── Preset 分頁 ──
                new_btn = pygame.Rect(px + pw - 96, py + 12, 80, 28)
                pygame.draw.rect(screen, (30, 80, 55), new_btn, border_radius=6)
                s = font.render(tr(cfg, "new_preset"), True, (190, 255, 210))
                screen.blit(s, (new_btn.centerx - s.get_width() // 2, new_btn.centery - s.get_height() // 2))
                hit_rects.append((new_btn, new_preset))

                if not presets:
                    screen.blit(font.render(tr(cfg, "no_presets"), True, (170, 170, 190)),
                                (px + 16, body_y + 8))
                max_scroll_p = max(0, len(presets) - visible_rows)
                key_scroll = min(key_scroll, max_scroll_p)
                shown_p = presets[key_scroll:key_scroll + visible_rows]
                for idx, name in enumerate(shown_p):
                    ry = body_y + idx * row_h
                    is_active = name == cfg["active_preset"]
                    nm = font.render(name, True, (150, 220, 255) if is_active else (210, 210, 220))
                    screen.blit(nm, (px + 16, ry + 8))
                    if is_active:
                        am = font.render(tr(cfg, "active_mark"), True, (120, 220, 160))
                        screen.blit(am, (px + 26 + nm.get_width(), ry + 8))
                    ap_btn = pygame.Rect(px + pw - 236, ry + 4, 66, 26)
                    sv_btn = pygame.Rect(px + pw - 162, ry + 4, 66, 26)
                    dl_btn = pygame.Rect(px + pw - 88, ry + 4, 66, 26)
                    for rect, txt, col, tcol in ((ap_btn, tr(cfg, "apply"), (28, 74, 99), (170, 220, 255)),
                                                 (sv_btn, tr(cfg, "save"), (55, 55, 75), (230, 230, 240)),
                                                 (dl_btn, tr(cfg, "delete"), (80, 45, 50), (240, 190, 190))):
                        pygame.draw.rect(screen, col, rect, border_radius=6)
                        s2 = font.render(txt, True, tcol)
                        screen.blit(s2, (rect.centerx - s2.get_width() // 2, rect.centery - s2.get_height() // 2))
                    hit_rects.append((ap_btn, (lambda n=name: apply_preset(n))))
                    hit_rects.append((sv_btn, (lambda n=name: save_preset(n))))
                    hit_rects.append((dl_btn, (lambda n=name: delete_preset(n))))
                if max_scroll_p > 0:
                    sc_txt = font.render(f"{key_scroll + 1}-{key_scroll + len(shown_p)} / {len(presets)}  {tr(cfg, 'scroll')}",
                                         True, (140, 140, 160))
                    screen.blit(sc_txt, (px + 16 + 200, py + 16))
                tip = font.render(tr(cfg, "tip_presets"), True, (140, 140, 160))

            screen.blit(tip, (px + 16, py + ph - 26))

        if layered:
            win_layered_update(hwnd, screen)
        else:
            pygame.display.flip()
        clock.tick(max(30, int(cfg["fps_limit"])))
        # 每 2 秒重新宣告一次置頂,避免被其他視窗搶走層級
        frame_count += 1
        if IS_WIN and frame_count % 120 == 0 and (layered or cfg["always_on_top"]):
            win_set_topmost(hwnd, True)
        if exit_after is not None and (now - app_start) > exit_after:
            running = False

    if state.recording:
        notes, t0 = state.stop_record()
        if notes:
            save_recording(cfg, notes, t0, time.time())
    pygame.quit()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        err = traceback.format_exc()
        with open(os.path.join(SCRIPT_DIR, "error.log"), "w", encoding="utf-8") as f:
            f.write(err)
        print(err)
        print("\n錯誤已寫入 error.log")
        try:
            input("按 Enter 離開...")
        except Exception:
            pass   # --noconsole 打包的 exe 沒有 stdin
        sys.exit(1)
