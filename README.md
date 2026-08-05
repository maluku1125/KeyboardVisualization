# Key Visualizer — 實況用即時按鍵可視化

按下的按鍵會以圓角方形沿時間軸滑動(像音遊譜面),長按會拉長,並顯示 KPS 統計。使用全域鍵盤監聽,遊戲視窗在前景時也能捕捉按鍵。

## 安裝與執行

```
pip install -r requirements.txt
python key_visualizer.py
```

先看效果(自動模擬按鍵):

```
python key_visualizer.py --demo
```

## 視窗內快捷鍵

| 鍵 | 功能 |
|---|---|
| F1 | 切換滑動方向(右→左 / 左→右) |
| F2 | 重置統計 |
| F3 | 開啟/關閉設定頁面 |
| F4 | 開始/停止錄製(錄製中顯示紅點) |
| ESC | 關閉設定頁面 / 離開 |

## 錄製與譜面檢視器

- **錄製**:F4 開始/停止,或在設定開「自動錄製」(啟動即錄,關閉程式自動存檔)。紀錄存在 `recordings/rec_日期時間.json`,包含所有按鍵事件、軌道、顏色、標籤與 base64 內嵌的按鍵圖片,單檔即可分享。
- **檢視器**:`index.html` 是純靜態網頁,拖放或選擇紀錄檔即顯示全程譜面。支援滾輪縮放、拖曳平移、點擊定位、播放(空白鍵或按鈕,可調 0.5×~4×)、KPS 曲線與統計。

### 放上 GitHub Pages

1. 在 GitHub 建一個 repo,把 `index.html` 放到根目錄(檔名保持 index.html)。
2. Repo → Settings → Pages → Source 選「Deploy from a branch」→ 選 main 分支 `/ (root)` → Save。
3. 幾分鐘後網址 `https://<帳號>.github.io/<repo名>/` 就能開檢視器。頁面純前端,紀錄檔只在瀏覽器本機解析,不會上傳到任何伺服器。

## 設定頁面 (F3)

分兩個分頁,改動即時生效並自動存回 `config.json`:

- **一般**:軌道數、背景透明度、顯示按壓長度(關閉後每次按壓顯示固定正方形)、滑動方向、滑動速度、統計列、綠幕模式。
- **按鍵**:直接列出整張鍵盤的按鍵(滾輪捲動),每個按鍵可以「圖片」選自訂圖示、✕ 清除圖示、「停用」不顯示該鍵、右側 − / + 指定固定軌道(「自動」表示動態分配)。

## 背景透明(僅 Windows)

「背景透明度」只影響背景,按鍵方塊保持不透明。調到 100% 以下會切換成無邊框、置頂的覆蓋視窗,可直接疊在遊戲畫面上,用滑鼠左鍵拖曳移動;0% 時背景完全穿透只剩按鍵。要調整設定按 F3(視窗需在焦點,可先點一下按鍵方塊或工作列圖示)。

## OBS 使用方式

1. 來源 → 視窗擷取 → 選 Key Visualizer 視窗。
2. 想去背:把 `config.json` 的 `chroma_key` 改成 `true`,背景會變綠色,再在 OBS 加「色度鍵」濾鏡即可。

## config.json 設定

| 欄位 | 說明 |
|---|---|
| `direction` | `"rtl"` 右→左,`"ltr"` 左→右 |
| `scroll_speed` | 滑動速度(像素/秒) |
| `track_all_keys` | `true` 監聽全部按鍵;`false` 只監聽 `tracked_keys` |
| `tracked_keys` | 自訂按鍵清單,每個按鍵固定一條軌道(順序即軌道順序) |
| `key_labels` | 自訂顯示文字,例如 `{"space": "␣", "z": "斬"}` |
| `key_icons` | 自訂圖片 icon,例如 `{"z": "icons/z.png"}`(路徑相對於程式資料夾,建議 PNG 透明背景) |
| `key_colors` | 個別按鍵顏色,例如 `{"z": "#FF6B9D"}` |
| `palette` | 未指定顏色時依軌道輪流使用的配色 |
| `default_color` | 設定後所有按鍵統一此色 |
| `max_lanes` | 全鍵模式下最多同時顯示的軌道數(不夠時回收最久沒用的) |
| `chroma_key` / `chroma_color` | OBS 色度去背用 |
| `show_stats` | 是否顯示上方 KPS 統計列 |

特殊按鍵名稱:`space` `enter` `shift` `ctrl` `alt` `tab` `esc` `up` `down` `left` `right` `f1`~`f12` 等(即 pynput 的名稱,左右 shift/ctrl/alt 已合併)。

## 注意

- 改完 `config.json` 需重新啟動程式。
- 部分防作弊遊戲可能阻擋全域鍵盤監聽。
