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
    """OSや環境に応じて利用可能な明朝体フォントのパスを返す"""
    # Streamlit Cloud（Linux環境）で一般的に使えるフォントを追加
    paths = [
        "/usr/share/fonts/truetype/fonts-japanese-mincho.ttf", # Linux用
        "C:\\Windows\\Fonts\\yumin.ttf",                      # Windows用
        "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc"          # Mac用
    ]
    for p in paths:
        if os.path.exists(p): return p
    return None

FONT_PATH = get_system_serif_font()

def get_exif_data(img):
    exif_data = {}
    try:
        info = img._getexif()
        if info:
            from PIL.ExifTags import TAGS
            for tag, value in info.items():
                decoded = TAGS.get(tag, tag)
                exif_data[decoded] = value
    except Exception:
        pass
            
    cam = exif_data.get("Model", "").strip()
    
    lens = exif_data.get("LensModel", "")
    if not lens and 0xA434 in exif_data:
        lens = exif_data[0xA434]
    if not lens:
        lens = exif_data.get("LensSpecification", "")
    lens = str(lens).strip()

    exposure_time = exif_data.get("ExposureTime", "")
    f_number = exif_data.get("FNumber", "")
    iso = exif_data.get("ISOSpeedRatings", "")
    if isinstance(iso, tuple) or isinstance(iso, list):
        iso = iso[0] if iso else ""

    if exposure_time:
        if exposure_time < 1.0:
            exposure_time = f"1/{int(round(1.0 / exposure_time))}"
        else:
            exposure_time = f"{exposure_time}"

    cond_list = []
    if exposure_time: cond_list.append(f"{exposure_time}s")
    if f_number: cond_list.append(f"f/{f_number}")
    if iso: cond_list.append(f"ISO{iso}")
    cond = "  ".join(cond_list)

    return cam, lens, cond

# ─── 画面UIの構築 ───
st.header("1. 作品情報を入力")
col1, col2 = st.columns(2)
with col1:
    input_m = st.text_input("メーカー名", placeholder="BANDAI, TAMIYA など")
    input_t = st.text_input("作品名（必須）", placeholder="HG ガンダム など")
with col2:
    input_s = st.text_input("シリーズ名", placeholder="宇宙世紀, HGUC など")

st.header("2. 画像をアップロード")
uploaded_files = st.file_uploader(
    "JPG / PNG 画像を選択（複数選択可）", 
    type=["jpg", "jpeg", "png"], 
    accept_multiple_files=True
)

# 処理実行
if uploaded_files and input_t.strip():
    st.header("3. 変換結果")
    
    center_text = input_t.strip()
    manufacturer_text = f"MFR: {input_m}" if input_m.strip() else ""
    series_text = f"SER: {input_s}" if input_s.strip() else ""
    left_sub_texts = [t for t in [manufacturer_text, series_text] if t != ""]

    border_thin_px = 50
    border_bottom_px = 160
    border_color = (255, 255, 255)
    text_color = (40, 40, 40)
    font_size_normal = 24
    font_size_large = 36

    for uploaded_file in uploaded_files:
        # 画像の読み込み
        img = Image.open(uploaded_file)
        width, height = img.size

        cam, lens, cond = get_exif_data(img)
        right_texts = [
            f"CAM: {cam}" if cam else "",
            f"LNS: {lens}" if lens else "",
            f"EXF: {cond}" if cond else ""
        ]
        right_texts = [t for t in right_texts if t != ""]

        # キャンバス作成
        new_width = width + (border_thin_px * 2)
        new_height = height + border_thin_px + border_bottom_px
        framed_img = Image.new('RGB', (new_width, new_height), color=border_color)
        framed_img.paste(img, (border_thin_px, border_thin_px))
        draw = ImageDraw.Draw(framed_img)

        # フォント設定
        try:
            if FONT_PATH and os.path.exists(FONT_PATH):
                font_normal = ImageFont.truetype(FONT_PATH, font_size_normal)
                font_large = ImageFont.truetype(FONT_PATH, font_size_large)
            else:
                font_normal = font_large = ImageFont.load_default()
        except Exception:
            font_normal = font_large = ImageFont.load_default()

        line_spacing = 8
        bottom_border_center_y = new_height - (border_bottom_px / 2)

        # 左下テキスト描画
        left_heights = []
        if center_text:
            bbox_c = draw.textbbox((0, 0), center_text, font=font_large)
            left_heights.append(bbox_c[3] - bbox_c[1])
        for t in left_sub_texts:
            bbox_s = draw.textbbox((0, 0), t, font=font_normal)
            left_heights.append(bbox_s[3] - bbox_s[1])
            
        if left_heights:
            total_left_height = sum(left_heights) + (line_spacing * (len(left_heights) - 1))
            current_y_left = bottom_border_center_y - (total_left_height / 2)
            if center_text:
                bbox_c = draw.textbbox((0, 0), center_text, font=font_large)
                draw.text((border_thin_px, current_y_left - bbox_c[1]), center_text, fill=text_color, font=font_large)
                current_y_left += (bbox_c[3] - bbox_c[1]) + line_spacing
            for t in left_sub_texts:
                bbox_s = draw.textbbox((0, 0), t, font=font_normal)
                draw.text((border_thin_px, current_y_left - bbox_s[1]), t, fill=text_color, font=font_normal)
                current_y_left += (bbox_s[3] - bbox_s[1]) + line_spacing

        # 右下テキスト描画
        if right_texts:
            right_bboxes = [draw.textbbox((0, 0), t, font=font_normal) for t in right_texts]
            right_widths = [b[2] - b[0] for b in right_bboxes]
            right_heights = [b[3] - b[1] for b in right_bboxes]
            total_right_height = sum(right_heights) + (line_spacing * (len(right_texts) - 1))
            
            current_y_right = bottom_border_center_y - (total_right_height / 2)
            for i, t in enumerate(right_texts):
                text_x = new_width - border_thin_px - right_widths[i]
                draw.text((text_x, current_y_right - right_bboxes[i][1]), t, fill=text_color, font=font_normal)
                current_y_right += right_heights[i] + line_spacing

        # 画面にプレビュー表示
        st.image(framed_img, caption=f"変換完了: {uploaded_file.name}", use_container_width=True)
        
        # ダウンロードボタンの設置
        buf = io.BytesIO()
        framed_img.save(buf, format="JPEG", quality=95)
        byte_im = buf.getvalue()
        
        st.download_button(
            label=f"📥 {uploaded_file.name} をダウンロード",
            data=byte_im,
            file_name=f"framed_{uploaded_file.name}",
            mime="image/jpeg"
        )
elif not input_t.strip() and uploaded_files:
    st.warning("⚠️ 枠を付けるには『作品名』を入力してください。")