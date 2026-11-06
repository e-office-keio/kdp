"""
KDP 表紙画像自動生成モジュール
商業出版クオリティのブックデザイン合成エンジン
- 電子書籍用（Kindle: 2560x1600）
- ペーパーバック用見開き展開表紙（300 DPI）
- AI生成アートワークの全面/帯付き合成、スマートグラデーション、洗練されたタイポグラフィ
"""
import os
import io
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from modules.cover_calculator import CoverDimensions, get_ebook_cover_dimensions

def find_japanese_font(size: int = 40, is_gothic: bool = False) -> ImageFont.FreeTypeFont:
    """利用可能な日本語TrueTypeフォントを自動検索"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ipa_mincho = os.path.join(base_dir, "fonts", "ipaexm.ttf")
    ipa_gothic = os.path.join(base_dir, "fonts", "ipaexg.ttf")
    
    if is_gothic and os.path.exists(ipa_gothic):
        try:
            return ImageFont.truetype(ipa_gothic, size)
        except Exception:
            pass
            
    if not is_gothic and os.path.exists(ipa_mincho):
        try:
            return ImageFont.truetype(ipa_mincho, size)
        except Exception:
            pass
            
    candidates = [
        ipa_gothic if is_gothic else ipa_mincho,
        "/System/Library/AssetsV2/com_apple_MobileAsset_Font8/0ebfdb7e5a2a1db668fa6209779e0725d6f6baba.asset/AssetData/BIZ_UDMincho-regular.ttf",
        "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()

def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    hex_clean = hex_str.lstrip("#")
    if len(hex_clean) == 6:
        return tuple(int(hex_clean[i:i+2], 16) for i in (0, 2, 4))
    return (26, 54, 93)

def create_ebook_cover_image(
    title: str,
    subtitle: str = "",
    author: str = "",
    catchphrase: str = "",  # 帯に載せるキャッチコピー
    theme_color: str = "#1A365D",
    accent_color: str = "#FFFFFF",
    center_image: Optional[Image.Image] = None,
    layout_style: str = "full_art",  # "full_art" (全面アート), "framed" (額縁帯付き), "minimal"
    is_vertical: bool = False
) -> Image.Image:
    """電子書籍用（Kindle: 1600 × 2560 px）表紙をプロクオリティで生成"""
    w, h = 1600, 2560
    base_rgb = hex_to_rgb(theme_color)
    accent_rgb = hex_to_rgb(accent_color)
    
    img = Image.new("RGB", (w, h), color=base_rgb)
    draw = ImageDraw.Draw(img)
    
    if center_image:
        art = center_image.convert("RGB")
        if layout_style == "full_art":
            # アートワークをアスペクト比を維持して画面上部〜全面に拡大配置
            art_ratio = art.width / art.height
            target_h = int(w / art_ratio)
            if target_h < h:
                # 画面全体を覆うようにスケーリング
                scale = max(w / art.width, h / art.height)
                new_w = int(art.width * scale)
                new_h = int(art.height * scale)
                art_resized = art.resize((new_w, new_h), Image.Resampling.LANCZOS)
                # 中央切り抜き
                crop_x = (new_w - w) // 2
                crop_y = (new_h - h) // 2
                art_cropped = art_resized.crop((crop_x, crop_y, crop_x + w, crop_y + h))
                img.paste(art_cropped, (0, 0))
            else:
                art_resized = art.resize((w, target_h), Image.Resampling.LANCZOS)
                img.paste(art_resized, (0, 0))
                
            # 文字を読みやすくするためのスマートグラデーションオーバーレイ
            # 上部（タイトル部）と下部（帯・著者部）に半透明の黒またはベースカラーを重ねる
            overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            
            # 上部グラデーション（タイトル視認性確保）
            gradient_h = int(h * 0.45)
            for y in range(gradient_h):
                alpha = int(220 * ((gradient_h - y) / gradient_h) ** 1.3)
                overlay_draw.line([(0, y), (w, y)], fill=(base_rgb[0], base_rgb[1], base_rgb[2], alpha))
                
            # 下部グラデーション（著者・帯視認性確保）
            grad_bottom_start = int(h * 0.65)
            for y in range(grad_bottom_start, h):
                alpha = int(240 * ((y - grad_bottom_start) / (h - grad_bottom_start)) ** 1.1)
                overlay_draw.line([(0, y), (w, y)], fill=(base_rgb[0], base_rgb[1], base_rgb[2], alpha))
                
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
            draw = ImageDraw.Draw(img)
            
        elif layout_style == "framed":
            # 額縁スタイル：中央にアートワーク、上下に美しい余白
            art_w = int(w * 0.85)
            art_h = int(h * 0.48)
            art_copy = art.copy()
            art_copy.thumbnail((art_w, art_h), Image.Resampling.LANCZOS)
            ax = (w - art_copy.width) // 2
            ay = int(h * 0.32)
            # アートワークの周りに細いフレーム
            draw.rectangle([ax - 4, ay - 4, ax + art_copy.width + 4, ay + art_copy.height + 4], outline=accent_color, width=2)
            img.paste(art_copy, (ax, ay))
    else:
        # 画像がない場合の幾何学デザイン装飾
        draw.rectangle([60, 60, w - 60, h - 60], outline=accent_color, width=3)
        draw.line([(w * 0.15, h * 0.48), (w * 0.85, h * 0.48)], fill=accent_color, width=2)

    # --- タイトル描画 ---
    title_font_size = 110 if len(title) <= 8 else (90 if len(title) <= 14 else 75)
    title_font = find_japanese_font(size=title_font_size, is_gothic=False)
    
    # 自動改行（1行8〜10文字程度）
    max_chars_line = 9 if len(title) > 9 else len(title)
    title_lines = [title[i:i + max_chars_line] for i in range(0, len(title), max_chars_line)]
    
    start_y = int(h * 0.12)
    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = (w - tw) // 2
        # ドロップシャドウ（影）を入れて文字をクッキリ浮き立たせる
        draw.text((x + 3, start_y + 3), line, fill=(0, 0, 0), font=title_font)
        draw.text((x, start_y), line, fill=accent_color, font=title_font)
        start_y += th + 28
        
    # --- サブタイトル描画 ---
    if subtitle:
        sub_font = find_japanese_font(size=44, is_gothic=True)
        sub_bbox = draw.textbbox((0, 0), subtitle, font=sub_font)
        sw = sub_bbox[2] - sub_bbox[0]
        sx = (w - sw) // 2
        draw.text((sx + 2, start_y + 12), subtitle, fill=(0, 0, 0), font=sub_font)
        draw.text((sx, start_y + 10), subtitle, fill=accent_color, font=sub_font)

    # --- 帯（オビ）＆キャッチコピー描画 ---
    if catchphrase:
        obi_h = 320
        obi_y = int(h * 0.72)
        # 半透明の帯プレート
        obi_plate = Image.new("RGBA", (w, obi_h), (0, 0, 0, 200))
        img.paste(obi_plate, (0, obi_y), mask=obi_plate)
        draw = ImageDraw.Draw(img)
        draw.line([(0, obi_y), (w, obi_y)], fill=accent_color, width=2)
        draw.line([(0, obi_y + obi_h), (w, obi_y + obi_h)], fill=accent_color, width=2)
        
        # キャッチコピー文字
        cp_font = find_japanese_font(size=46, is_gothic=True)
        cp_lines = [catchphrase[i:i + 18] for i in range(0, len(catchphrase), 18)]
        cy = obi_y + 45
        for cpline in cp_lines[:3]:
            cbbox = draw.textbbox((0, 0), cpline, font=cp_font)
            cw = cbbox[2] - cbbox[0]
            draw.text(((w - cw) // 2, cy), cpline, fill="#FACC15", font=cp_font)  # イエローゴールドで目を引く
            cy += 65

    # --- 著者名描画 ---
    if author:
        author_font = find_japanese_font(size=56, is_gothic=False)
        author_text = f"{author} 著" if not author.endswith("著") else author
        abbox = draw.textbbox((0, 0), author_text, font=author_font)
        aw = abbox[2] - abbox[0]
        ax = (w - aw) // 2
        ay = int(h * 0.90)
        draw.text((ax + 2, ay + 2), author_text, fill=(0, 0, 0), font=author_font)
        draw.text((ax, ay), author_text, fill=accent_color, font=author_font)
        
    return img

def create_paperback_cover_image(
    dims: CoverDimensions,
    title: str,
    subtitle: str = "",
    author: str = "",
    back_description: str = "",
    catchphrase: str = "",
    theme_color: str = "#1A365D",
    accent_color: str = "#FFFFFF",
    center_image: Optional[Image.Image] = None,
    layout_style: str = "full_art",
    is_vertical: bool = False
) -> Image.Image:
    """
    ペーパーバック用展開表紙（裏表紙 + 背表紙 + 表表紙 + 裁ち落とし）を300DPIでプロ仕様生成
    """
    w = dims.total_width_px
    h = dims.total_height_px
    base_rgb = hex_to_rgb(theme_color)
    accent_rgb = hex_to_rgb(accent_color)
    
    img = Image.new("RGB", (w, h), color=base_rgb)
    draw = ImageDraw.Draw(img)
    
    spine_left = dims.spine_x_px
    spine_right = dims.spine_x_px + dims.spine_width_px
    front_x = dims.front_cover_x_px
    front_w = w - front_x - dims.bleed_px
    front_h = h - (dims.bleed_px * 2)
    
    # --- 1. 表表紙側のアートワーク配置 ---
    if center_image:
        art = center_image.convert("RGB")
        # 表表紙エリア（front_x ~ front_x + front_w）にアートを配置
        scale = max(front_w / art.width, h / art.height)
        new_w = int(art.width * scale)
        new_h = int(art.height * scale)
        art_resized = art.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        crop_x = (new_w - front_w) // 2
        crop_y = (new_h - h) // 2
        art_cropped = art_resized.crop((crop_x, crop_y, crop_x + front_w, crop_y + h))
        img.paste(art_cropped, (front_x, 0))
        
        # 表表紙側のグラデーションオーバーレイ
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        
        grad_h = int(h * 0.45)
        for y in range(grad_h):
            alpha = int(220 * ((grad_h - y) / grad_h) ** 1.3)
            overlay_draw.line([(front_x, y), (w, y)], fill=(base_rgb[0], base_rgb[1], base_rgb[2], alpha))
            
        grad_bot = int(h * 0.65)
        for y in range(grad_bot, h):
            alpha = int(240 * ((y - grad_bot) / (h - grad_bot)) ** 1.1)
            overlay_draw.line([(front_x, y), (w, y)], fill=(base_rgb[0], base_rgb[1], base_rgb[2], alpha))
            
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)
    else:
        draw.rectangle(
            [front_x + 60, dims.bleed_px + 60, front_x + front_w - 60, h - dims.bleed_px - 60],
            outline=accent_color,
            width=2
        )
        
    # --- 表表紙のテキスト描画 ---
    title_font_size = 80 if len(title) <= 10 else 64
    title_font = find_japanese_font(size=title_font_size, is_gothic=False)
    
    max_c = 10 if len(title) > 10 else len(title)
    title_lines = [title[i:i + max_c] for i in range(0, len(title), max_c)]
    
    t_y = int(h * 0.16)
    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = front_x + (front_w - tw) // 2
        draw.text((x + 3, t_y + 3), line, fill=(0, 0, 0), font=title_font)
        draw.text((x, t_y), line, fill=accent_color, font=title_font)
        t_y += th + 24
        
    if subtitle:
        sub_font = find_japanese_font(size=36, is_gothic=True)
        sbbox = draw.textbbox((0, 0), subtitle, font=sub_font)
        sw = sbbox[2] - sbbox[0]
        sx = front_x + (front_w - sw) // 2
        draw.text((sx + 2, t_y + 12), subtitle, fill=(0, 0, 0), font=sub_font)
        draw.text((sx, t_y + 10), subtitle, fill=accent_color, font=sub_font)
        
    if catchphrase:
        # 表表紙側のオビ
        obi_h = 280
        obi_y = int(h * 0.72)
        obi_plate = Image.new("RGBA", (front_w, obi_h), (0, 0, 0, 210))
        img.paste(obi_plate, (front_x, obi_y), mask=obi_plate)
        draw = ImageDraw.Draw(img)
        draw.line([(front_x, obi_y), (front_x + front_w, obi_y)], fill=accent_color, width=2)
        draw.line([(front_x, obi_y + obi_h), (front_x + front_w, obi_y + obi_h)], fill=accent_color, width=2)
        
        cp_font = find_japanese_font(size=40, is_gothic=True)
        cp_lines = [catchphrase[i:i + 16] for i in range(0, len(catchphrase), 16)]
        cy = obi_y + 40
        for cpline in cp_lines[:3]:
            cbbox = draw.textbbox((0, 0), cpline, font=cp_font)
            cw = cbbox[2] - cbbox[0]
            draw.text((front_x + (front_w - cw) // 2, cy), cpline, fill="#FACC15", font=cp_font)
            cy += 55
            
    if author:
        a_font = find_japanese_font(size=46, is_gothic=False)
        author_text = f"{author} 著"
        abbox = draw.textbbox((0, 0), author_text, font=a_font)
        aw = abbox[2] - abbox[0]
        ax = front_x + (front_w - aw) // 2
        ay = int(h * 0.88)
        draw.text((ax + 2, ay + 2), author_text, fill=(0, 0, 0), font=a_font)
        draw.text((ax, ay), author_text, fill=accent_color, font=a_font)

    # --- 2. 背表紙領域 (中央) ---
    draw.rectangle([spine_left, 0, spine_right, h], fill=theme_color)
    draw.line([(spine_left, 0), (spine_left, h)], fill=accent_color, width=1)
    draw.line([(spine_right, 0), (spine_right, h)], fill=accent_color, width=1)
    
    if dims.can_have_spine_text and dims.spine_width_px >= 36:
        spine_font_size = min(36, max(18, int(dims.spine_width_px * 0.55)))
        spine_font = find_japanese_font(size=spine_font_size, is_gothic=True)
        
        sy = int(h * 0.18)
        for char in list(title):
            cbbox = draw.textbbox((0, 0), char, font=spine_font)
            cw = cbbox[2] - cbbox[0]
            ch_h = cbbox[3] - cbbox[1]
            cx = spine_left + (dims.spine_width_px - cw) // 2
            draw.text((cx, sy), char, fill=accent_color, font=spine_font)
            sy += ch_h + 8
            if sy > h * 0.65:
                break
                
        if author:
            asy = int(h * 0.80)
            for char in list(author):
                cbbox = draw.textbbox((0, 0), char, font=spine_font)
                cw = cbbox[2] - cbbox[0]
                ch_h = cbbox[3] - cbbox[1]
                cx = spine_left + (dims.spine_width_px - cw) // 2
                draw.text((cx, asy), char, fill=accent_color, font=spine_font)
                asy += ch_h + 8
                if asy > h * 0.92:
                    break

    # --- 3. 裏表紙領域 (左側) ---
    back_x = dims.bleed_px
    back_w = spine_left - back_x
    
    if back_description:
        desc_font = find_japanese_font(size=28, is_gothic=False)
        dy = int(h * 0.22)
        margin_x = back_x + 80
        max_desc_w = back_w - 160
        chars_per_line = max(15, int(max_desc_w / 32))
        
        for line in back_description.split("\n"):
            line_str = line.strip()
            if not line_str:
                dy += 25
                continue
            for idx in range(0, len(line_str), chars_per_line):
                sub = line_str[idx:idx + chars_per_line]
                draw.text((margin_x, dy), sub, fill=accent_color, font=desc_font)
                dy += 44
                if dy > h * 0.70:
                    break
                    
    # バーコード領域
    barcode_w = 400
    barcode_h = 240
    bx = back_x + back_w - barcode_w - 60
    by = h - dims.bleed_px - barcode_h - 60
    draw.rectangle([bx, by, bx + barcode_w, by + barcode_h], outline=accent_color, width=1)
    info_font = find_japanese_font(size=20, is_gothic=True)
    draw.text((bx + 55, by + 105), "※KDPバーコード配置エリア", fill=accent_color, font=info_font)
    
    return img
