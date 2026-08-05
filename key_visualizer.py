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
    "show_stats": True,
    "font_name": "microsoftjhenghei,msyh,arial",
    "min_note_px": 18
}

# 按鍵頁顯示的完整鍵盤清單(pynput 名稱)
ALL_KEYS = (
    list("abcdefghijklmnopqrstuvwxyz") + list("0123456789")
    + [f"f{i}" for i in range(1, 13)]
    + ["space", "enter", "shift", "ctrl", "alt", "tab", "esc", "backspace",
       "caps_lock", "delete", "insert", "home", "end", "page_up", "page_down",
       "up", "down", "left", "right",
       "-", "=", "[", "]", "\\", ";", "'", ",", ".", "/", "`"]
)


def hex_to_rgb(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
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

    def press(self, key, now):
        with self.lock:
            if key in self.disabled or key in self.active:
                return
            note = {"key": key, "start": now, "end": None}
            self.active[key] = note
            self.press_times.append(now)
            self.total += 1

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
        state.press(normalize_key(key), time.time())

    def on_release(key):
        state.release(normalize_key(key), time.time())

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
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

    def win_set_topmost(hwnd, on):
        _user32.SetWindowPos(hwnd, HWND_TOPMOST if on else HWND_NOTOPMOST,
                             0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

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


# ── 一般設定項目 ──────────────────────────────────────────
SETTING_ITEMS = [
    {"id": "max_lanes", "label": "軌道數", "type": "int", "min": 1, "max": 16, "step": 1},
    {"id": "background_opacity", "label": "背景透明度 (0%=穿透)", "type": "pct", "min": 0.0, "max": 1.0, "step": 0.05},
    {"id": "show_hold", "label": "顯示按壓長度 (關=正方形)", "type": "bool"},
    {"id": "direction", "label": "滑動方向", "type": "choice", "choices": ["rtl", "ltr"],
     "names": {"rtl": "右 → 左", "ltr": "左 → 右"}},
    {"id": "scroll_speed", "label": "滑動速度", "type": "int", "min": 60, "max": 600, "step": 20},
    {"id": "show_stats", "label": "顯示統計列", "type": "bool"},
    {"id": "chroma_key", "label": "綠幕模式 (OBS 色度去背)", "type": "bool"},
]


def value_text(cfg, item):
    v = cfg[item["id"]]
    t = item["type"]
    if t == "bool":
        return "開" if v else "關"
    if t == "pct":
        return f"{int(round(v * 100))}%"
    if t == "choice":
        return item["names"][v]
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
    if demo:
        start_demo(state)
    else:
        try:
            start_listener(state)
        except Exception as e:
            print(f"[error] 無法啟動全域鍵盤監聽: {e}")
            print("        可先用  python key_visualizer.py --demo  預覽效果")
            return

    pygame.init()
    W, H = int(cfg["window_width"]), int(cfg["window_height"])
    pygame.display.set_caption("Key Visualizer  |  F1 方向  F2 重置  F3 設定  ESC 離開")
    clock = pygame.time.Clock()

    display = None
    hwnd = None
    layered = False

    def setup_window(want_layered):
        nonlocal display, hwnd, layered
        want_layered = want_layered and IS_WIN
        flags = pygame.NOFRAME if want_layered else pygame.RESIZABLE
        display = pygame.display.set_mode((W, H), flags)
        layered = want_layered
        if IS_WIN:
            hwnd = win_get_hwnd()
            win_set_layered(hwnd, layered)
            win_set_topmost(hwnd, layered)

    setup_window(cfg["background_opacity"] < 0.999)

    font = pygame.font.SysFont(cfg["font_name"], 16)
    font_big = pygame.font.SysFont(cfg["font_name"], 22, bold=True)

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
        save_config(cfg)

    def color_of(key, lane):
        if key in key_colors:
            return key_colors[key]
        if default_color:
            return default_color
        return palette[lane % len(palette)]

    def label_of(key):
        return cfg["key_labels"].get(key, key.upper())

    # ── 按鍵頁動作 ──
    def choose_icon(key):
        path = pick_image_file()
        if path and load_icon(key, path):
            cfg["key_icons"][key] = path
            icon_cache.pop(key, None)
            thumb_cache.pop(key, None)
            save_config(cfg)

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

    settings_open = False
    settings_page = "general"
    key_scroll = 0
    hit_rects = []
    drag = None            # (cursor_x0, cursor_y0, win_x0, win_y0)

    all_keys_order = list(ALL_KEYS)

    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.VIDEORESIZE and not layered:
                W, H = ev.w, ev.h
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
            elif ev.type == pygame.MOUSEWHEEL and settings_open and settings_page == "keys":
                key_scroll = max(0, key_scroll - ev.y)

        if drag and IS_WIN:
            if pygame.mouse.get_pressed()[0]:
                cx, cy = win_cursor_pos()
                win_move_window(hwnd, drag[2] + cx - drag[0], drag[3] + cy - drag[1])
            else:
                drag = None

        now = time.time()
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
        if cfg["show_stats"]:
            stats = f"KPS {kps:>2}   MAX {max_kps:>2}   TOTAL {total}"
            screen.blit(font_big.render(stats, True, (240, 240, 245)), (12, 10))
            hint = font.render("F3 設定", True, (150, 150, 170))
            screen.blit(hint, (W - hint.get_width() - 12, 4))
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
        edge_x = W - 1 if direction == "rtl" else 1
        pygame.draw.line(screen, (255, 255, 255), (edge_x, top), (edge_x, H - 6), 2)

        # ── 設定頁面 ──
        hit_rects = []
        if settings_open:
            pw = 560
            visible_rows = 9
            row_h = 38
            known_keys = all_keys_order + sorted(
                (set(cfg["key_icons"]) | set(cfg["fixed_lanes"]) | set(cfg["disabled_keys"])
                 | set(lanes.last_used)) - set(all_keys_order))
            n_rows = len(SETTING_ITEMS) if settings_page == "general" else visible_rows
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

            tabs = [("general", "一般"), ("keys", "按鍵")]
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
                for idx, item in enumerate(SETTING_ITEMS):
                    ry = body_y + idx * row_h
                    screen.blit(font.render(item["label"], True, (210, 210, 220)), (px + 16, ry + 8))
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
                tip = font.render("點 − / + 或按鈕切換,改動立即儲存 (F3/ESC 關閉)", True, (140, 140, 160))
            else:
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
                    s = font.render("圖片", True, (230, 230, 240))
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
                    dis_btn = pygame.Rect(px + 268, ry + 4, 56, 26)
                    pygame.draw.rect(screen, (90, 50, 55) if disabled else (55, 55, 75),
                                     dis_btn, border_radius=6)
                    s = font.render("已停用" if disabled else "停用", True,
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
                    vtxt = "自動" if fl is None else f"軌道 {fl + 1}"
                    vs = font.render(vtxt, True, (150, 220, 255) if fl is None else (255, 214, 120))
                    screen.blit(vs, ((minus.right + plus.left - vs.get_width()) // 2, ry + 8))
                    hit_rects.append((minus, (lambda k=key: shift_fixed_lane(k, -1))))
                    hit_rects.append((plus, (lambda k=key: shift_fixed_lane(k, +1))))
                sc_txt = font.render(f"{key_scroll + 1}-{key_scroll + len(shown)} / {len(known_keys)}  (滾輪捲動)",
                                     True, (140, 140, 160))
                screen.blit(sc_txt, (px + pw - sc_txt.get_width() - 16, py + 16))
                tip = font.render("「圖片」選檔、✕ 清除、停用不顯示;右側 − / + 固定軌道", True, (140, 140, 160))

            screen.blit(tip, (px + 16, py + ph - 26))

        if layered:
            win_layered_update(hwnd, screen)
        else:
            pygame.display.flip()
        clock.tick(60)

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
        except EOFError:
            pass
        sys.exit(1)
