"""
KDP 表紙サイズ計算モジュール
KDP公式仕様に基づくペーパーバック・電子書籍の表紙サイズおよび背表紙厚みの精密計算
"""
from dataclasses import dataclass
from typing import Dict, Tuple

# 主要な判型（幅(mm), 高さ(mm), 表示名, 英語呼称）
TRIM_SIZES: Dict[str, Dict[str, float]] = {
    "shiroku": {
        "name": "四六判 (127 × 188 mm)",
        "width_mm": 127.0,
        "height_mm": 188.0,
        "desc": "文芸書・単行本・一般書に最適（日本KDPで最もポピュラー）"
    },
    "a5": {
        "name": "A5判 (148 × 210 mm)",
        "width_mm": 148.0,
        "height_mm": 210.0,
        "desc": "教科書・学術書・ビジネス書・テキスト・マニュアル"
    },
    "b6": {
        "name": "B6判 (128 × 182 mm)",
        "width_mm": 128.0,
        "height_mm": 182.0,
        "desc": "一般単行本・エッセイ・コミックサイズ"
    },
    "bunko": {
        "name": "文庫判 / A6相当 (105 × 148 mm)",
        "width_mm": 105.0,
        "height_mm": 148.0,
        "desc": "持ち歩きやすい文庫本・掌編小説"
    },
    "shinsho": {
        "name": "新書判 (105 × 173 mm)",
        "width_mm": 105.0,
        "height_mm": 173.0,
        "desc": "新書・教養書・コンパクトビジネス書"
    },
    "b5": {
        "name": "B5判 (182 × 257 mm)",
        "width_mm": 182.0,
        "height_mm": 257.0,
        "desc": "大型雑誌・問題集・図録・資料集"
    },
    "us_trade": {
        "name": "標準米判 (6 × 9 インチ / 152.4 × 228.6 mm)",
        "width_mm": 152.4,
        "height_mm": 228.6,
        "desc": "海外Amazon・洋書で標準的なトレードペーパーバック"
    },
}

# 1ページあたりの厚み係数 (mm)
# 白用紙: 0.002252 インチ = 0.0572008 mm
# クリーム用紙: 0.0025 インチ = 0.0635 mm
# カラー用紙: 0.002347 インチ = 0.0596138 mm
PAPER_THICKNESS_MM = {
    "white": 0.0572,
    "cream": 0.0635,
    "color": 0.0596,
}

# 裁ち落とし (Bleed) : 0.125 インチ = 3.175 mm
BLEED_MM = 3.175
DPI = 300  # KDP推奨の印刷解像度 (300 DPI)
MM_TO_INCH = 1.0 / 25.4

@dataclass
class CoverDimensions:
    trim_name: str
    page_count: int
    paper_type: str
    
    trim_width_mm: float
    trim_height_mm: float
    spine_width_mm: float
    
    total_width_mm: float
    total_height_mm: float
    bleed_mm: float
    
    # 300 DPI でのピクセルサイズ
    total_width_px: int
    total_height_px: int
    spine_width_px: int
    bleed_px: int
    front_cover_x_px: int
    back_cover_x_px: int
    spine_x_px: int
    
    can_have_spine_text: bool  # 79ページ以上で背表紙テキスト推奨

def calculate_paperback_cover(
    trim_key: str,
    page_count: int,
    paper_type: str = "white",
    custom_width_mm: float = 0.0,
    custom_height_mm: float = 0.0
) -> CoverDimensions:
    """ペーパーバック表紙全体の寸法を計算する"""
    if trim_key == "custom":
        w_mm = custom_width_mm
        h_mm = custom_height_mm
        trim_name = f"カスタム判型 ({w_mm:.1f} × {h_mm:.1f} mm)"
    else:
        info = TRIM_SIZES.get(trim_key, TRIM_SIZES["shiroku"])
        w_mm = info["width_mm"]
        h_mm = info["height_mm"]
        trim_name = info["name"]
    
    thickness_per_page = PAPER_THICKNESS_MM.get(paper_type, 0.0572)
    spine_mm = page_count * thickness_per_page
    
    # 全幅 = 裁ち落とし(左) + 裏表紙 + 背表紙 + 表表紙 + 裁ち落とし(右)
    total_w_mm = (BLEED_MM * 2) + (w_mm * 2) + spine_mm
    total_h_mm = (BLEED_MM * 2) + h_mm
    
    def mm_to_px(val_mm: float) -> int:
        return int(round(val_mm * MM_TO_INCH * DPI))
    
    total_w_px = mm_to_px(total_w_mm)
    total_h_px = mm_to_px(total_h_mm)
    spine_w_px = mm_to_px(spine_mm)
    bleed_px = mm_to_px(BLEED_MM)
    
    # 各セクションの開始X座標 (左から：裏表紙 -> 背表紙 -> 表表紙)
    # 0 ~ bleed: 裁ち落とし
    # bleed ~ bleed + w: 裏表紙
    # bleed + w ~ bleed + w + spine: 背表紙
    # bleed + w + spine ~ ...: 表表紙
    back_x_px = bleed_px
    spine_x_px = bleed_px + mm_to_px(w_mm)
    front_x_px = spine_x_px + spine_w_px
    
    can_spine_text = page_count >= 79
    
    return CoverDimensions(
        trim_name=trim_name,
        page_count=page_count,
        paper_type=paper_type,
        trim_width_mm=round(w_mm, 2),
        trim_height_mm=round(h_mm, 2),
        spine_width_mm=round(spine_mm, 2),
        total_width_mm=round(total_w_mm, 2),
        total_height_mm=round(total_h_mm, 2),
        bleed_mm=round(BLEED_MM, 2),
        total_width_px=total_w_px,
        total_height_px=total_h_px,
        spine_width_px=spine_w_px,
        bleed_px=bleed_px,
        front_cover_x_px=front_x_px,
        back_cover_x_px=back_x_px,
        spine_x_px=spine_x_px,
        can_have_spine_text=can_spine_text,
    )

def get_ebook_cover_dimensions() -> Dict[str, int]:
    """電子書籍用（Kindle）の推奨解像度"""
    return {
        "width_px": 1600,
        "height_px": 2560,
        "aspect_ratio": 1.6,
        "desc": "KDP推奨理想解像度 (2560 x 1600 px, 縦横比 1.6:1)"
    }
