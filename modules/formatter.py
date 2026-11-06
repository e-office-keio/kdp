"""
日本語原稿フォーマッター・組版整形モジュール
KDP・Kindle標準の美しい日本語表記への自動整形
"""
import re
from typing import Dict, Any

def format_japanese_text(
    text: str,
    fix_ellipsis: bool = True,
    fix_dash: bool = True,
    fix_exclamation_space: bool = True,
    indent_paragraphs: bool = True,
    normalize_quotes: bool = True,
    is_vertical: bool = False
) -> str:
    """日本語原稿をKDP標準に自動整形する"""
    lines = text.split("\n")
    formatted_lines = []
    
    for line in lines:
        l = line
        
        # 見出し行（# で始まる行）や空行は字下げせずスキップ
        if not l.strip() or l.strip().startswith("#"):
            formatted_lines.append(l)
            continue
            
        # 1. 引用符・括弧の正規化
        if normalize_quotes:
            # 半角のかぎ括弧等を全角に
            l = l.replace("｢", "「").replace("｣", "」")
            l = l.replace("『", "『").replace("』", "』")
            
        # 2. 三点リーダーの正規化（... や 。。。 や … 1つ を …… に）
        if fix_ellipsis:
            # 3つ以上のドットやピリオド、句点
            l = re.sub(r'(\.{3,}|…{1,}|。{3,})', '……', l)
            # 奇数個の … を偶数（2の倍数）に調整
            l = re.sub(r'……+', '……', l)
            
        # 3. ダッシュ・罫線の正規化（-- や ――― を ―― に）
        if fix_dash:
            l = re.sub(r'(--+|――+|──+|ーー+)', '――', l)
            
        # 4. 感嘆符・疑問符の後の全角スペース
        if fix_exclamation_space:
            # 半角!?を全角！？に置換
            l = l.replace("?", "？").replace("!", "！")
            # ！？の直後が閉じ括弧（」』)）や行末以外の場合、全角スペースを入れる
            l = re.sub(r'([！？])(?![」』）\s　\n]|$)', r'\1　', l)
            
        # 5. 行頭の字下げ（全角1文字空け）
        if indent_paragraphs:
            stripped = l.lstrip()
            # 会話文（「『（ など）で始まらない場合のみ字下げ
            if stripped and not stripped.startswith(("「", "『", "（", "【", "“", "”", "［", "[", "<", "《")):
                l = "　" + stripped
                
        # 6. 縦書き特有の処理（オプション）
        if is_vertical:
            # 縦書き時の「〜」「～」を「〜」や縦書き用波ダッシュに補正
            # 縦書きで寝てしまうコロンやハイフンの補正等
            l = l.replace("~", "〜").replace("～", "〜")
            
        formatted_lines.append(l)
        
    return "\n".join(formatted_lines)
