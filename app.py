import io
import os
import re
import sys
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# 画面のタイトル設定
st.set_page_config(page_title="プラモ画像 データ刻印ツール", layout="centered")
st.title("📸 プラモ画像 データ刻印ツール")
st.write("画像からExif（撮影情報）の自動取得を試みます。読み込めない場合は手動入力も可能です。")

def get_available_fonts():
    """環境ごとに利用可能なフォントのパスと名前のマッピングを返す"""
    # 候補となるフォント設定 (名前: パス)
    font_candidates = {
        "Noto Serif JP (同梱フォント)": "NotoSerifJP-Regular.ttf",
        # Windows
        "游明朝 (Windows)": "C:\\Windows\\Fonts\\yumin.ttf",
        "游ゴシック (Windows)": "C:\\Windows\\Fonts\\yuitalic.ttf",
        "メイリオ (Windows)": "C:\\Windows\\Fonts\\meiryo.ttc",
        "MS Pゴシック (Windows)": "C:\\Windows\\Fonts\\msgothic.ttc",
        "MS P明朝 (Windows)": "C:\\Windows\\Fonts\\msmincho.ttc",
        # Mac
        "ヒラギノ明朝 ProN (Mac)": "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc",
        "ヒラギノ角ゴ ProN (Mac)": "/System/Library/Fonts/ヒラギノ角ゴ ProN.ttc",
        "クレー (Mac)": "/System/Library/Fonts/Klee.ttc",
        # Linux / Streamlit Cloud用バックアップ
        "Noto Sans CJK (Linux)": "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "IPAex明朝 (Linux)": "/usr/share/fonts/truetype/ipaexfont/ipaexm.ttf",
        "IPAexゴシック (Linux)": "/usr/share/fonts/truetype/ipaexfont/ipaexg.ttf",
        "D標音ゴシック (Linux)": "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
        "D標音明朝 (Linux)": "/usr/share/fonts/truetype/fonts-japanese-mincho.ttf",
    }
    
    # 実際に存在するフォントだけを絞り込む
    available = {}
    for name, path in font_candidates.items():
        if os.path.exists(path):
            available[name] = path
            
    # もし一つも見つからなかった場合のセーフティ
    if not available:
        available["システム標準フォント"] = "DEFAULT"
        
    return available

# 利用可能なフォントリストを取得
AVAILABLE_FONTS = get_available_fonts()

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

# HEXカラーコードをRGBタプルに変換する関数
def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

# ─── 画面UIの構築 ───
st.header("1. 作品情報を入力")
col1, col2 = st.columns(2)
with col1:
    input_m = st.text_input("メーカー名", placeholder="BANDAI, TAMIYA など")
    input_t = st.text_input("作品名（必須）", placeholder="HG ガンダム など")
with col2:
    input_s = st.text_input("シリーズ名", placeholder="宇宙世紀, HGUC など")

# ─── 撮影データの手動入力 ───
st.header("2. 撮影情報を入力（Exifがない場合や書き換えたい場合）")
col_e1, col_e2, col_e3 = st.columns(3)
with col_e1:
    manual_cam = st.text_input("カメラ名（任意）", placeholder="Sony α7IV, iPhone 15 など")
with col_e2:
    manual_lens = st.text_input("レンズ名（任意）", placeholder="FE 35mm F1.4 など")
with col_e3:
    manual_cond = st.text_input("撮影条件（任意）", placeholder="1/125s  f/2.8  ISO400 など")

# ─── デザイン・位置設定 ───
st.header("3. デザインと配置を設定")
col_c1, col_c2 = st.columns(2)
with col_c1:
    text_color_hex = st.color_picker("文字の色を選んでください", "#FFFFFF")
with col_c2:
    position_option = st.selectbox(
        "文字を配置する場所",
        ["左下（作品名）＆ 右下（撮影データ）", 
         "左上（作品名）＆ 右上（撮影データ）", 
         "左下（すべて配置）", 
         "右下（すべて配置）"]
    )

col_f1, col_f2 = st.columns(2)
with col_f1:
    # 【新機能】フォントの選択ボックス
    selected_font_name = st.selectbox(
        "使用するフォント",
        options=list(AVAILABLE_FONTS.keys())
    )
    selected_font_path = AVAILABLE_FONTS[selected_font_name]
with col_f2:
    pass

col_size1, col_size2 = st.columns(2)
with col_size1:
    font_size_large = st.slider("作品名の文字サイズ", min_value=12, max_value=72, value=36, step=2)
with col_size2:
    font_size_normal = st.slider("その他の文字サイズ", min_value=12, max_value=72, value=24, step=2)

st.header("4. 画像をアップロード")
uploaded_files = st.file_uploader(
    "JPG / PNG 画像を選択（複数選択可）", 
    type=["jpg", "jpeg", "png"], 
    accept_multiple_files=True
)

# 処理実行
if uploaded_files and input_t.strip():
    st.header("5. 変換結果")
    
    center_text = input_t.strip()
    manufacturer_text = f"MFR: {input_m}" if input_m.strip() else ""
    series_text = f"SER: {input_s}" if input_s.strip() else ""
    left_sub_texts = [t for t in [manufacturer_text, series_text] if t != ""]

    text_color = hex_to_rgb(text_color_hex)
    margin_px = 30  # 画像の端からの余白

    for uploaded_file in uploaded_files:
        # まずは生の状態で画像を開く（Exifを保持するため）
        raw_img = Image.open(uploaded_file)

        # Exifデータの自動取得を「RGBAに変換する前」に実行する
        cam, lens, cond = get_exif_data(raw_img)

        # Exif抽出後に、描画レイヤー処理のためRGBAに変換する
        base_img = raw_img.convert("RGBA")
        width, height = base_img.size
        
        # もし自動取得できず、かつ手動入力があればそちらを採用する
        if not cam and manual_cam.strip(): cam = manual_cam.strip()
        if not lens and manual_lens.strip(): lens = manual_lens.strip()
        if not cond and manual_cond.strip(): cond = manual_cond.strip()

        right_texts = [
            f"CAM: {cam}" if cam else "",
            f"LNS: {lens}" if lens else "",
            f"EXF: {cond}" if cond else ""
        ]
        right_texts = [t for t in [r for r in right_texts if r != ""]]

        txt_layer = Image.new("RGBA", base_img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)

        # 【新機能対応】選択されたフォントの読み込み処理
        try:
            if selected_font_path != "DEFAULT" and os.path.exists(selected_font_path):
                font_normal = ImageFont.truetype(selected_font_path, font_size_normal)
                font_large = ImageFont.truetype(selected_font_path, font_size_large)
            else:
                font_normal = font_large = ImageFont.load_default()
        except Exception:
            font_normal = font_large = ImageFont.load_default()

        line_spacing = 8

        # ─── 各テキストのサイズ計算 ───
        left_heights = []
        if center_text:
            bbox_c = draw.textbbox((0, 0), center_text, font=font_large)
            left_heights.append(bbox_c[3] - bbox_c[1])
        for t in left_sub_texts:
            bbox_s = draw.textbbox((0, 0), t, font=font_normal)
            left_heights.append(bbox_s[3] - bbox_s[1])
        total_left_height = sum(left_heights) + (line_spacing * (len(left_heights) - 1)) if left_heights else 0

        if right_texts:
            right_bboxes = [draw.textbbox((0, 0), t, font=font_normal) for t in right_texts]
            right_widths = [b[2] - b[0] for b in right_bboxes]
            right_heights = [b[3] - b[1] for b in right_bboxes]
            total_right_height = sum(right_heights) + (line_spacing * (len(right_texts) - 1))
        else:
            total_right_height = right_widths = right_heights = right_bboxes = 0

        # ─── 配置エリアの計算 ───
        is_top = "右上" in position_option or "左上" in position_option
        is_split = "＆" in position_option

        if is_split:
            text_zone_height = max(total_left_height, total_right_height) + (margin_px * 2)
        else:
            text_zone_height = total_left_height + total_right_height + (line_spacing if total_left_height and total_right_height else 0) + (margin_px * 2)

        if is_top:
            center_y = text_zone_height / 2
        else:
            center_y = height - (text_zone_height / 2)

        # ─── 文字描画 ───
        if position_option == "左下（作品名）＆ 右下（撮影データ）" or position_option == "左上（作品名）＆ 右上（撮影データ）":
            if left_heights:
                current_y_left = center_y - (total_left_height / 2)
                if center_text:
                    bbox_c = draw.textbbox((0, 0), center_text, font=font_large)
                    draw.text((margin_px, current_y_left - bbox_c[1]), center_text, fill=text_color + (255,), font=font_large)
                    current_y_left += (bbox_c[3] - bbox_c[1]) + line_spacing
                for t in left_sub_texts:
                    bbox_s = draw.textbbox((0, 0), t, font=font_normal)
                    draw.text((margin_px, current_y_left - bbox_s[1]), t, fill=text_color + (255,), font=font_normal)
                    current_y_left += (bbox_s[3] - bbox_s[1]) + line_spacing

            if right_texts:
                current_y_right = center_y - (total_right_height / 2)
                for i, t in enumerate(right_texts):
                    text_x = width - margin_px - right_widths[i]
                    draw.text((text_x, current_y_right - right_bboxes[i][1]), t, fill=text_color + (255,), font=font_normal)
                    current_y_right += right_heights[i] + line_spacing

        else:
            x_pos = margin_px if "左下" in position_option else None
            current_y = center_y - (text_zone_height - margin_px * 2) / 2
            
            if center_text:
                bbox_c = draw.textbbox((0, 0), center_text, font=font_large)
                final_x = x_pos if x_pos is not None else width - margin_px - (bbox_c[2] - bbox_c[0])
                draw.text((final_x, current_y - bbox_c[1]), center_text, fill=text_color + (255,), font=font_large)
                current_y += (bbox_c[3] - bbox_c[1]) + line_spacing
            for t in left_sub_texts:
                bbox_s = draw.textbbox((0, 0), t, font=font_normal)
                final_x = x_pos if x_pos is not None else width - margin_px - (bbox_s[2] - bbox_s[0])
                draw.text((final_x, current_y - bbox_s[1]), t, fill=text_color + (255,), font=font_normal)
                current_y += (bbox_s[3] - bbox_s[1]) + line_spacing
                
            if left_heights and right_texts:
                current_y += line_spacing
                
            if right_texts:
                for i, t in enumerate(right_texts):
                    final_x = x_pos if x_pos is not None else width - margin_px - right_widths[i]
                    draw.text((final_x, current_y - right_bboxes[i][1]), t, fill=text_color + (255,), font=font_normal)
                    current_y += right_heights[i] + line_spacing

        # 合成
        final_img = Image.alpha_composite(base_img, txt_layer).convert("RGB")

        # プレビュー表示
        st.image(final_img, caption=f"変換完了: {uploaded_file.name}", use_container_width=True)
        
        # ダウンロード
        buf = io.BytesIO()
        final_img.save(buf, format="JPEG", quality=95)
        byte_im = buf.getvalue()
        
        st.download_button(
            label=f"📥 {uploaded_file.name} をダウンロード",
            data=byte_im,
            file_name=f"marked_{uploaded_file.name}",
            mime="image/jpeg"
        )
elif not input_t.strip() and uploaded_files:
    st.warning("⚠️ 文字を入れるには『作品名』を入力してください。")
