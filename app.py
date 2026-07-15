import io
import os
import re
import sys
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# 画面のタイトル設定
st.set_page_config(page_title="プラモ画像 枠付けツール", layout="centered")
st.title("📸 プラモ画像 枠付けツール")
st.write("画像をアップロードするだけで、上品な白枠とExifデータを追加します。")

def get_system_serif_font():
    """GitHubに一緒に上げたフォントファイルを最優先で読み込む"""
    # ─── 【修正】同じフォルダに置いたフォントファイルを指定 ───
    local_font = "NotoSerifJP-Regular.ttf" 
    
    if os.path.exists(local_font):
        return local_font
        
    # 見つからない場合のバックアップ
    paths = [
        "/usr/share/fonts/truetype/fonts-japanese-mincho.ttf",
        "C:\\Windows\\Fonts\\yumin.ttf",
        "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc"
    ]
    for p in paths:
        if os.path.exists(p): return p
    return None

FONT_PATH = get_system_serif_font()

# --- この下の get_exif_data 以降のコードはすべてそのままでOKです！ ---