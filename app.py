import io
import os
import re
import sys
import glob
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# 左右分割レイアウト
st.set_page_config(page_title="プラモ画像 データ刻印ツール", layout="wide")

st.title("📸 プラモ画像 データ刻印ツール")
st.write("作品情報内の日本語と英数字を自動判別し、別々のフォントで綺麗にミックスして刻印します。")

def get_available_fonts():
    available = {}
    local_fonts = glob.glob("*.ttf") + glob.glob("*.otf") + glob.glob("*.ttc")
    for path in local_fonts:
        name = os.path.splitext(os.path.basename(path))[0]
        available[f"📁 {name}"] = path

    font_candidates = {
        "游明朝 (Windows)": "C:\\Windows\\Fonts\\yumin.ttf",
        "游ゴシック (Windows)": "C:\\Windows\\Fonts\\yuitalic.ttf",
        "メイリオ (Windows)": "C:\\Windows\\Fonts\\meiryo.ttc",
        "MS Pゴシック (Windows)": "C:\\Windows\\Fonts\\msgothic.ttc",
        "MS P明朝 (Windows)": "C:\\Windows\\Fonts\\msmincho.ttc",
        "ヒラギノ明朝 ProN (Mac)": "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc",
        "ヒラギノ角ゴ ProN (Mac)": "/System/Library/Fonts/ヒラギノ角ゴ ProN.ttc",
        "クレー (Mac)": "/System/Library/Fonts/Klee.ttc",
        "Noto Sans CJK (Linux)": "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    }
    for name, path in font_candidates.items():
        if os.path.exists(path):
            available[name] = path
            
    if not available:
        available["システム標準フォント"] = "DEFAULT"
    return available

VOLUME_FONTS = get_available_fonts()

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

# ─── 【重要】日英混植のための判定＆描画ロジック ───
def split_ja_en(text):
    """文字列を英数字ブロックと日本語ブロックに分解する"""
    # 半角英数字、スペース、記号の連続にマッチする正規表現
    tokens = re.split(r'([A-Za-z0-9\s\-\.\,\:\/\(\)\[\]\&\#\+\=\_\*\!\?]+)', text)
    return [t for t in tokens if t]

def draw_mixed_text(draw, x, y, text, font_ja, font_en, fill):
    """日本語と英語のフォントを切り替えながら横一行に描画する"""
    current_x = x
    blocks = split_ja_en(text)
    for block in blocks:
        # ブロックが英数字のみ（または空白・記号）で構成されているか判定
        is_en = re.match(r'^[A-Za-z0-9\s\-\.\,\:\/\(\)\[\]\&\#\+\=\_\*\!\?]+$', block)
        font = font_en if is_en else font_ja
        
        # 描画
        draw.text((current_x, y), block, font=font, fill=fill)
        
        # 次の文字の描画位置をずらすための幅を計算
        bbox = draw.textbbox((0, 0), block, font=font)
        current_x += (bbox[2] - bbox[0])

def get_mixed_text_size(draw, text, font_ja, font_en):
    """混植テキスト全体の幅と高さを計算する"""
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
        ["左下（作品名）＆ 右下（撮影データ）", "左上（作品名）＆ 右上（撮影データ）", "左下（すべて配置）", "右下（すべて配置）"]
    )

    font_options = list(VOLUME_FONTS.keys())
    selected_jp_font_name = st.selectbox("ベースにする日本語フォント", options=font_options, index=0)
    selected_jp_font_path = VOLUME_FONTS[selected_jp_font_name]

    default_en_index = min(1, len(font_options) - 1)
    selected_en_font_name = st.selectbox("英数字用の英語フォント", options=font_options, index=default_en_index)
    selected_en_font_path = VOLUME_FONTS[selected_en_font_name]

    font_size_large = st.slider("作品名の文字サイズ", min_value=12, max_value=72, value=36, step=2)
    font_size_normal = st.slider("その他の文字サイズ", min_value=12, max_value=72, value=24, step=2)

    st.header("4. 画像をアップロード")
    uploaded_files = st.file_uploader("JPG / PNG 画像を選択（複数選択可）", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

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

            # 各フォントオブジェクトの用意（大サイズ・通常サイズ）
            try:
                if selected_jp_font_path != "DEFAULT" and os.path.exists(selected_jp_font_path):
                    f_jp_l = ImageFont.truetype(selected_jp_font_path, font_size_large)
                    f_jp_n = ImageFont.truetype(selected_jp_font_path, font_size_normal)
                else:
                    f_jp_l = f_jp_n = ImageFont.load_default()

                if selected_en_font_path != "DEFAULT" and os.path.exists(selected_en_font_path):
                    f_en_l = ImageFont.truetype(selected_en_font_path, font_size_large)
                    f_en_n = ImageFont.truetype(selected_en_font_path, font_size_normal)
                else:
                    f_en_l = f_en_n = ImageFont.load_default()
            except Exception:
                f_jp_l = f_jp_n = f_en_l = f_en_n = ImageFont.load_default()

            line_spacing = 8

            # ─── 高さと幅の計算（混植対応版） ───
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
                w, h = get_mixed_text_size(draw, t, f_jp_n, f_en_n) # 撮影データも一応混植対応
                right_heights.append(h)
                right_widths.append(w)
            total_right_height = sum(right_heights) + (line_spacing * (len(right_texts) - 1)) if right_texts else 0

            is_top = "右上" in position_option or "左上" in position_option
            is_split = "＆" in position_option

            if is_split:
                text_zone_height = max(total_left_height, total_right_height) + (margin_px * 2)
            else:
                text_zone_height = total_left_height + total_right_height + (line_spacing if total_left_height and total_right_height else 0) + (margin_px * 2)

            center_y = text_zone_height / 2 if is_top else height - (text_zone_height / 2)

            # ─── 描画処理（混植関数を呼び出し） ───
            fill_color = text_color + (255,)

            if is_split:
                # 【分割配置モード】左側に作品情報、右側に撮影データ
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
                # 【片側寄せモード】すべてを片側にまとめて配置
                x_pos = margin_px if "左下" in position_option else None
                current_y = center_y - (text_zone_height - margin_px * 2) / 2
                
                if center_text:
                    final_x = x_pos if x_pos is not None else width - margin_px - left_widths[0]
                    draw_mixed_text(draw, final_x, current_y, center_text, f_jp_l, f_en_l, fill_color)
                    current_y += left_heights[0] + line_spacing
                for i, t in enumerate(left_sub_texts):
                    idx_offset = 1 if center_text else 0
                    final_x = x_pos if x_pos is not None else width - margin_px - left_widths[i + idx_offset]
                    draw_mixed_text(draw, final_x, current_y, t, f_jp_n, f_en_n, fill_color)
                    current_y += left_heights[i + idx_offset] + line_spacing
                    
                if left_heights and right_texts:
                    current_y += line_spacing
                    
                if right_texts:
                    for i, t in enumerate(right_texts):
                        final_x = x_pos if x_pos is not None else width - margin_px - right_widths[i]
                        draw_mixed_text(draw, final_x, current_y, t, f_jp_n, f_en_n, fill_color)
                        current_y += right_heights[i] + line_spacing

            final_img = Image.alpha_composite(base_img, txt_layer).convert("RGB")
            
            with current_col:
                st.image(final_img, caption=f"変換完了: {uploaded_file.name}", use_container_width=True)
                buf = io.BytesIO()
                final_img.save(buf, format="JPEG", quality=95)
                byte_im = buf.getvalue()
                
                st.download_button(
                    label=f"📥 ダウンロード ({uploaded_file.name})",
                    data=byte_im,
                    file_name=f"marked_{uploaded_file.name}",
                    mime="image/jpeg",
                    key=f"dl_{idx}"
                )
                st.write("---")

    elif not input_t.strip() and uploaded_files:
        st.warning("⚠️ 文字を入れるには、左側パネルで『作品名』を入力してください。")
    else:
        st.info("💡 左側パネルで情報を入力し、画像をアップロードするとここに結果が表示されます。")
