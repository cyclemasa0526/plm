import io
import os
import re
import sys
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# 左右分割レイアウト
st.set_page_config(page_title="プラモ画像 データ刻印ツール", layout="wide")

st.title("📸 プラモ画像 データ刻印ツール")
st.write("作品情報内の日本語と英数字を自動判別し、別々のフォント（Noto Serif JP × Oswald）で綺麗にミックスして刻印します。")

# 使用するフォントファイルを固定定義
FONT_PATH_JA = "NotoSerifJP-Regular.ttf"
FONT_PATH_EN = "Oswald-VariableFont_wght.ttf"

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

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def split_ja_en(text):
    tokens = re.split(r'([A-Za-z0-9\s\-\.\,\:\/\(\)\[\]\&\#\+\=\_\*\!\?]+)', text)
    return [t for t in tokens if t]

def draw_mixed_text(draw, x, y, text, font_ja, font_en, fill):
    current_x = x
    blocks = split_ja_en(text)
    for block in blocks:
        is_en = re.match(r'^[A-Za-z0-9\s\-\.\,\:\/\(\)\[\]\&\#\+\=\_\*\!\?]+$', block)
        font = font_en if is_en else font_ja
        draw.text((current_x, y), block, font=font, fill=fill)
        bbox = draw.textbbox((0, 0), block, font=font)
        current_x += (bbox[2] - bbox[0])

def get_mixed_text_size(draw, text, font_ja, font_en):
    total_width = 0
    max_height = 0
    blocks = split_ja_en(text)
    for block in blocks:
        is_en = re.match(r'^[A-Za-z0-9\s\-\.\,\:\/\(\)\[\]\&\#\+\=\_\*\!\?]+$', block)
        font = font_en if is_en else font_ja
        bbox = draw.textbbox((0, 0), block, font=font)
        total_width += (bbox[2] - bbox[0])
        max_height = max(max_height, bbox[3] - bbox[1])
    return total_width, max_height


# ─── 画面UIの構築（左右分割） ───
left_panel, right_panel = st.columns([4, 6])

with left_panel:
    st.header("1. 作品情報を入力")
    input_m = st.text_input("メーカー名", placeholder="BANDAI, TAMIYA など")
    input_t = st.text_input("作品名（必須）", placeholder="HG ガンダム RX-78-2 など")
    input_s = st.text_input("シリーズ名", placeholder="宇宙世紀, HGUC など")

    st.header("2. 撮影情報を入力")
    manual_cam = st.text_input("カメラ名（任意）", placeholder="Sony α7IV など")
    manual_lens = st.text_input("レンズ名（任意）", placeholder="FE 35mm F1.4 など")
    manual_cond = st.text_input("撮影条件（任意）", placeholder="1/125s f/2.8 ISO400 など")

    st.header("3. デザインと配置を設定")
    text_color_hex = st.color_picker("文字の色を選んでください", "#000000")
    
    position_option = st.selectbox(
        "文字を配置する場所",
        ["左下（作品名）＆ 右下（撮影データ）", 
         "左上（作品名）＆ 右上（撮影データ）", 
         "左下（すべて配置）", 
         "右下（すべて配置）",
         "左上（すべて配置）",
         "右上（すべて配置）"]
    )

    st.caption("※フォントは「Noto Serif JP」(日本語) と 「Oswald」(英数字) に固定されています。")

    font_size_large = st.slider("作品名の文字サイズ", min_value=12, max_value=72, value=36, step=2)
    font_size_normal = st.slider("その他の文字サイズ", min_value=12, max_value=72, value=24, step=2)
    
    line_spacing = st.slider("行間の広さ（余白）", min_value=0, max_value=40, value=16, step=2)

    st.header("4. 画像をアップロード")
    uploaded_files = st.file_uploader("JPG / PNG 画像を選択（複数選択可）", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

    # 【新機能】ファイル名変更のプレビュー表示
    if uploaded_files:
        st.write("📁 **保存時のファイル名（予定）:**")
        prefix = input_t.strip() if input_t.strip() else "未入力"
        for f in uploaded_files:
            st.caption(f" ┗ `{prefix}_{f.name}`")

# ─── 右側：変換結果の表示エリア ───
with right_panel:
    st.header("5. 変換結果")
    
    if uploaded_files and input_t.strip():
        center_text = input_t.strip()
        manufacturer_text = f"MFR: {input_m}" if input_m.strip() else ""
        series_text = f"SER: {input_s}" if input_s.strip() else ""
        left_sub_texts = [t for t in [manufacturer_text, series_text] if t != ""]

        text_color = hex_to_rgb(text_color_hex)
        margin_px = 30
        result_cols = st.columns(2)

        for idx, uploaded_file in enumerate(uploaded_files):
            current_col = result_cols[idx % 2]
            raw_img = Image.open(uploaded_file)
            cam, lens, cond = get_exif_data(raw_img)

            base_img = raw_img.convert("RGBA")
            width, height = base_img.size
            
            if not cam and manual_cam.strip(): cam = manual_cam.strip()
            if not lens and manual_lens.strip(): lens = manual_lens.strip()
            if not cond and manual_cond.strip(): cond = manual_cond.strip()

            right_texts = [f"CAM: {cam}" if cam else "", f"LNS: {lens}" if lens else "", f"EXF: {cond}" if cond else ""]
            right_texts = [t for t in [r for r in right_texts if r != ""]]

            txt_layer = Image.new("RGBA", base_img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(txt_layer)

            try:
                if os.path.exists(FONT_PATH_JA):
                    f_jp_l = ImageFont.truetype(FONT_PATH_JA, font_size_large)
                    f_jp_n = ImageFont.truetype(FONT_PATH_JA, font_size_normal)
                else:
                    f_jp_l = f_jp_n = ImageFont.load_default()

                if os.path.exists(FONT_PATH_EN):
                    f_en_l = ImageFont.truetype(FONT_PATH_EN, font_size_large)
                    f_en_n = ImageFont.truetype(FONT_PATH_EN, font_size_normal)
                else:
                    f_en_l = f_en_n = ImageFont.load_default()
            except Exception:
                f_jp_l = f_jp_n = f_en_l = f_en_n = ImageFont.load_default()

            # 各テキストのサイズ計算
            left_heights = []
            left_widths = []
            if center_text:
                w, h = get_mixed_text_size(draw, center_text, f_jp_l, f_en_l)
                left_heights.append(h)
                left_widths.append(w)
            for t in left_sub_texts:
                w, h = get_mixed_text_size(draw, t, f_jp_n, f_en_n)
                left_heights.append(h)
                left_widths.append(w)
            total_left_height = sum(left_heights) + (line_spacing * (len(left_heights) - 1)) if left_heights else 0

            right_heights = []
            right_widths = []
            for t in right_texts:
                w, h = get_mixed_text_size(draw, t, f_jp_n, f_en_n)
                right_heights.append(h)
                right_widths.append(w)
            total_right_height = sum(right_heights) + (line_spacing * (len(right_texts) - 1)) if right_texts else 0

            # 配置の判定
            is_top = "上" in position_option
            is_split = "＆" in position_option

            fill_color = text_color + (255,)

            if is_split:
                text_zone_height = max(total_left_height, total_right_height) + (margin_px * 2)
                if is_top:
                    center_y = margin_px + (text_zone_height - margin_px * 2) / 2
                else:
                    center_y = height - margin_px - (text_zone_height - margin_px * 2) / 2

                if left_heights:
                    current_y_left = center_y - (total_left_height / 2)
                    if center_text:
                        draw_mixed_text(draw, margin_px, current_y_left, center_text, f_jp_l, f_en_l, fill_color)
                        current_y_left += left_heights[0] + line_spacing
                    for i, t in enumerate(left_sub_texts):
                        idx_offset = 1 if center_text else 0
                        draw_mixed_text(draw, margin_px, current_y_left, t, f_jp_n, f_en_n, fill_color)
                        current_y_left += left_heights[i + idx_offset] + line_spacing

                if right_texts:
                    current_y_right = center_y - (total_right_height / 2)
                    for i, t in enumerate(right_texts):
                        text_x = width - margin_px - right_widths[i]
                        draw_mixed_text(draw, text_x, current_y_right, t, f_jp_n, f_en_n, fill_color)
                        current_y_right += right_heights[i] + line_spacing
            else:
                total_all_lines = len(left_heights) + len(right_heights)
                total_all_height = sum(left_heights) + sum(right_heights) + (line_spacing * (total_all_lines - 1) if total_all_lines > 0 else 0)

                if is_top:
                    current_y = margin_px
                else:
                    current_y = height - margin_px - total_all_height

                x_pos = margin_px if "左" in position_option else None
                
                if center_text:
                    final_x = x_pos if x_pos is not None else width - margin_px - left_widths[0]
                    draw_mixed_text(draw, final_x, current_y, center_text, f_jp_l, f_en_l, fill_color)
                    current_y += left_heights[0] + line_spacing
                for i, t in enumerate(left_sub_texts):
                    idx_offset = 1 if center_text else 0
                    final_x = x_pos if x_pos is not None else width - margin_px - left_widths[i + idx_offset]
                    draw_mixed_text(draw, final_x, current_y, t, f_jp_n, f_en_n, fill_color)
                    current_y += left_heights[i + idx_offset] + line_spacing
                    
                if right_texts:
                    for i, t in enumerate(right_texts):
                        final_x = x_pos if x_pos is not None else width - margin_px - right_widths[i]
                        draw_mixed_text(draw, final_x, current_y, t, f_jp_n, f_en_n, fill_color)
                        current_y += right_heights[i] + line_spacing

            final_img = Image.alpha_composite(base_img, txt_layer).convert("RGB")
            
            # 【修正】保存時のダウンロードファイル名を「作品名_元のファイル名」に変更
            download_filename = f"{center_text}_{uploaded_file.name}"

            with current_col:
                st.image(final_img, caption=f"変換完了: {uploaded_file.name}", use_container_width=True)
                buf = io.BytesIO()
                final_img.save(buf, format="JPEG", quality=95)
                byte_im = buf.getvalue()
                
                st.download_button(
                    label=f"📥 ダウンロード ({uploaded_file.name})",
                    data=byte_im,
                    file_name=download_filename,
                    mime="image/jpeg",
                    key=f"dl_{idx}"
                )
                st.write("---")

    elif not input_t.strip() and uploaded_files:
        st.warning("⚠️ 文字を入れるには、左側パネルで『作品名』を入力してください。")
    else:
        st.info("💡 左側パネルで情報を入力し、画像をアップロードするとここに結果が表示されます。")
