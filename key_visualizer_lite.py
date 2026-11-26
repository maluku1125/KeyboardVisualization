"""Key Visualizer Lite — 無錄製版。

與 key_visualizer.py 共用全部程式碼,但完全關閉錄製功能:
F4 無作用、不會自動錄製、設定頁不顯示錄製選項,也不會寫出任何按鍵紀錄檔。
"""
import key_visualizer as kv

kv.RECORDING_AVAILABLE = False

if __name__ == "__main__":
    kv.run()
