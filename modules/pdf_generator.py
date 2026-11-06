"""
ペーパーバック（紙書籍）用 高品位PDF組版エンジン
KDP公式推奨の判型・余白（ノド/小口見開き切り替え）・ノンブル（ページ番号）付きPDF出力
JIS X 4051準拠の日本語禁則処理 ＋ 文字間均等割り付け（両端揃え）による商業出版クオリティ
"""
import io
import os
import xml.sax.saxutils as saxutils
from unicodedata import category
from typing import List, Optional, Tuple, Dict

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate,
    PageTemplate,
    Frame,
    Paragraph,
    Spacer,
    PageBreak,
    HRFlowable
)
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
import reportlab.lib.textsplit as ts
import reportlab.platypus.paragraph as para_mod

from modules.cover_calculator import TRIM_SIZES
from modules.document_parser import ChapterSection

# ----------------- 日本語禁則処理と両端揃え（モンキーパッチ） -----------------

# JIS X 4051 準拠：行頭禁則文字（行頭に来てはいけない文字）
CANNOT_START = set(
    "!?,.:;)]}、。」』】〕］）々―ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮーヵヶ゛゜・ヽヾゝゞ°′″℃％‰!?！？)]｝〉》」』】〕"
)
# JIS X 4051 準拠：行末禁則文字（行末に来てはいけない文字）
CANNOT_END = set("([{「『【〔［（“‘〈《")

def patched_dumbSplit(word, widths, maxWidths):
    """
    日本語組版に特化した正確な行分割アルゴリズム
    - 英単語・数字で行末に達した際、行の半分まで不必要に巻き戻されるReportLabのバグを解消
    - JIS X 4051準拠の行頭禁則・行末禁則を厳密に処理
    """
    if not isinstance(maxWidths, (list, tuple)):
        maxWidths = [maxWidths]
    lines = []
    i = 0
    widthUsed = 0
    lineStartPos = 0
    maxWidth = maxWidths[0]
    nW = len(word)
    _FUZZ = 1e-6

    while i < nW:
        w = widths[i]
        c = word[i]
        widthUsed += w
        i += 1

        if widthUsed > maxWidth + _FUZZ and widthUsed > 0:
            split_idx = i - 1

            # 1. 英数字が連続している場合、英単語の開始位置まで最小限戻る（最大20文字）
            if ord(c) < 0x3000 and c.isalnum():
                lookback_limit = max(lineStartPos + 1, split_idx - 20)
                for j in range(split_idx, lookback_limit, -1):
                    cj = word[j]
                    if not cj.isalnum() or ord(cj) >= 0x3000 or category(cj) == 'Zs':
                        split_idx = j + 1
                        break

            # 2. 行頭禁則処理: split_idxの文字が行頭禁則文字なら、さらに1文字前に戻す
            if split_idx < nW and word[split_idx] in CANNOT_START and split_idx > lineStartPos + 1:
                split_idx -= 1

            # 3. 行末禁則処理: 直前の文字が行末禁則文字（「『（等）なら、その文字を次行へ送る
            if split_idx > lineStartPos + 1 and word[split_idx - 1] in CANNOT_END:
                split_idx -= 1

            line_text = word[lineStartPos:split_idx].rstrip()
            actual_w = sum(widths[lineStartPos:split_idx])
            extraSpace = maxWidth - actual_w
            lines.append([extraSpace, line_text])

            try:
                maxWidth = maxWidths[len(lines)]
            except IndexError:
                maxWidth = maxWidths[-1]

            lineStartPos = split_idx
            i = split_idx
            widthUsed = 0

    if lineStartPos < nW:
        remaining_text = word[lineStartPos:]
        actual_w = sum(widths[lineStartPos:])
        lines.append([maxWidth - actual_w, remaining_text])

    return lines

ts.dumbSplit = patched_dumbSplit

def patched_justifyDrawParaLine(tx, offset, extraspace, words, last=0):
    """
    日本語（CJK）に対応した両端揃え（均等割り付け）
    空白文字（スペース）だけでなく、文字間スペース（setCharSpace）を均等配分し、
    すべての行末が右端ラインにピタリと揃うように描画
    """
    para_mod.setXPos(tx, offset)
    text = ' '.join(words)
    simple = getattr(tx, 'preformatted', False) or (-1e-8 < extraspace <= 1e-8) or (last and extraspace > -1e-8)
    
    if simple:
        tx._textOut(text, 1)
    else:
        nChars = len(text) - 1
        nSpaces = len(words) + para_mod._nbspCount(text) - 1
        cjk_chars = sum(1 for ch in text if ord(ch) >= 0x3000)

        # CJK文字主体の行（文字間均等割り付け）
        if cjk_chars > len(text) * 0.3 and nChars > 0:
            char_space = extraspace / float(nChars)
            # 安全リミット（行末余白が広すぎる段落末尾等の崩れを防ぐ）
            if char_space <= 3.8:
                tx.setCharSpace(char_space)
                tx._textOut(text, 1)
                tx.setCharSpace(0)
            else:
                tx._textOut(text, 1)
        elif nSpaces > 0:
            tx.setWordSpace(extraspace / float(nSpaces))
            tx._textOut(text, 1)
            tx.setWordSpace(0)
        else:
            tx._textOut(text, 1)

    para_mod.setXPos(tx, -offset)
    return offset

para_mod._justifyDrawParaLine = patched_justifyDrawParaLine

def patched_justifyDrawParaLineX(tx, offset, line, last=0):
    """複数フラグメント用の両端揃えパッチ"""
    tx._x_offset = offset
    para_mod.setXPos(tx, offset)
    extraSpace = line.extraSpace
    simple = line.lineBreak or (-1e-8 < extraSpace <= 1e-8) or (last and extraSpace > -1e-8)
    if not simple:
        # フラグメント内の文字数を数えて文字間均等割り付け
        total_text = "".join([getattr(w, 'text', str(w)) for w in line.words if not hasattr(w, 'cbDefn')])
        nChars = len(total_text) - 1
        cjk_chars = sum(1 for ch in total_text if ord(ch) >= 0x3000)
        if cjk_chars > len(total_text) * 0.3 and nChars > 0:
            char_space = extraSpace / float(nChars)
            if char_space <= 3.8:
                tx.setCharSpace(char_space)
                para_mod._putFragLine(offset, tx, line, last, 'justify')
                tx.setCharSpace(0)
            else:
                para_mod._putFragLine(offset, tx, line, last, 'justify')
        else:
            nSpaces = line.wordCount + sum([para_mod._nbspCount(w.text) for w in line.words if not hasattr(w, 'cbDefn')]) - 1
            if nSpaces > 0:
                tx.setWordSpace(extraSpace / float(nSpaces))
                para_mod._putFragLine(offset, tx, line, last, 'justify')
                tx.setWordSpace(0)
            else:
                para_mod._putFragLine(offset, tx, line, last, 'justify')
    else:
        para_mod._putFragLine(offset, tx, line, last, 'justify')
    para_mod.setXPos(tx, -offset)

para_mod._justifyDrawParaLineX = patched_justifyDrawParaLineX

# ----------------- フォント選択肢の定義 -----------------

FONT_STYLES: Dict[str, Dict[str, str]] = {
    "ipaex_mincho": {
        "name": "端正なクラシック明朝（IPAex明朝）",
        "desc": "文芸書・小説・単行本に最も適した、伝統的で美しい明朝体。長文でも目が疲れません。",
        "body_font": "IPAexMincho",
        "heading_font": "IPAexGothic"
    },
    "biz_ud_mincho": {
        "name": "現代的で読みやすい明朝（モリサワ BIZ UD明朝）",
        "desc": "ビジネス書・実用書・学術テキストに最適。文字が潰れにくくくっきり読めるユニバーサルデザイン明朝。",
        "body_font": "BizUDMincho",
        "heading_font": "BizUDMincho"
    },
    "heisei_mincho": {
        "name": "標準出版明朝（平成明朝体）",
        "desc": "日本のDTP・出版界で長年採用されてきた、堅実で格式のあるCID明朝体。",
        "body_font": "HeiseiMin-W3",
        "heading_font": "HeiseiKakuGo-W5"
    },
    "ipaex_gothic": {
        "name": "クリアな現代ゴシック（IPAexゴシック）",
        "desc": "IT技術書・マニュアル・自己啓発書など、明るくモダンで視認性を最重視したい本に。",
        "body_font": "IPAexGothic",
        "heading_font": "IPAexGothic"
    },
    "heisei_gothic": {
        "name": "標準出版ゴシック（平成角ゴシック）",
        "desc": "力強いゴシック体。タイトルや重要箇所の強調が際立つレイアウトに。",
        "body_font": "HeiseiKakuGo-W5",
        "heading_font": "HeiseiKakuGo-W5"
    }
}

def register_fonts():
    """利用可能なフォントを自動登録"""
    # 1. 組み込みCIDフォント
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))
        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    except Exception:
        pass

    # 2. アプリ同梱のIPAexフォント
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ipa_mincho_path = os.path.join(base_dir, "fonts", "ipaexm.ttf")
    ipa_gothic_path = os.path.join(base_dir, "fonts", "ipaexg.ttf")
    
    if os.path.exists(ipa_mincho_path):
        try:
            pdfmetrics.registerFont(TTFont("IPAexMincho", ipa_mincho_path))
        except Exception:
            pass
            
    if os.path.exists(ipa_gothic_path):
        try:
            pdfmetrics.registerFont(TTFont("IPAexGothic", ipa_gothic_path))
        except Exception:
            pass

    # 3. MacのBIZ UD明朝 (TrueType)
    biz_candidates = [
        "/System/Library/AssetsV2/com_apple_MobileAsset_Font8/0ebfdb7e5a2a1db668fa6209779e0725d6f6baba.asset/AssetData/BIZ_UDMincho-regular.ttf",
        "/Library/Fonts/BIZ-UDMinchoM.ttc",
        "/Library/Fonts/BIZUDMincho-Regular.ttf",
    ]
    for path in biz_candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("BizUDMincho", path))
                break
            except Exception:
                continue

register_fonts()

class NumberedCanvas(canvas.Canvas):
    """
    2パス処理で総ページ数を把握し、ノンブル（ページ番号）および柱（ヘッダー）を
    見開き（奇数・偶数ページ）に合わせて正しく描画するCanvas
    """
    def __init__(self, *args, **kwargs):
        self.is_vertical = kwargs.pop("is_vertical", False)
        self.header_font = kwargs.pop("header_font", "HeiseiKakuGo-W5")
        self.book_title = kwargs.pop("book_title", "")
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages: int):
        # 扉ページ（1ページ目）はノンブル・柱を印字しない
        if self._pageNumber == 1:
            return
            
        page_w = self._pagesize[0]
        page_h = self._pagesize[1]
        
        self.saveState()
        safe_header = self.header_font if self.header_font in pdfmetrics.getRegisteredFontNames() else "HeiseiKakuGo-W5"
        self.setFont(safe_header, 8.5)
        self.setFillColor(colors.HexColor("#666666"))
        
        page_num_str = str(self._pageNumber)
        is_odd = (self._pageNumber % 2 == 1)
        margin_bottom = 11 * mm
        margin_top = page_h - 11 * mm
        
        if not self.is_vertical:
            # 横書き（左開き）
            # 奇数ページ（右ページ）: ノンブルは右下、柱は右上
            # 偶数ページ（左ページ）: ノンブルは左下、柱は左上
            if is_odd:
                self.drawRightString(page_w - 14 * mm, margin_bottom, page_num_str)
                if self.book_title and self._pageNumber > 2:
                    self.drawRightString(page_w - 14 * mm, margin_top, self.book_title[:28])
            else:
                self.drawString(14 * mm, margin_bottom, page_num_str)
                if self.book_title and self._pageNumber > 2:
                    self.drawString(14 * mm, margin_top, self.book_title[:28])
        else:
            # 縦書き（右開き）
            if is_odd:
                self.drawString(14 * mm, margin_bottom, page_num_str)
            else:
                self.drawRightString(page_w - 14 * mm, margin_bottom, page_num_str)
                
        self.restoreState()

class BookDocTemplate(BaseDocTemplate):
    """
    KDPペーパーバック専用：見開き（奇数ページ・偶数ページ）でノド・小口のマージンを
    自動切り替えするドキュメントテンプレート
    """
    def __init__(self, filename, page_w, page_h, is_vertical=False,
                 gutter=17 * mm, outer=13 * mm, top=17 * mm, bottom=17 * mm, **kw):
        super().__init__(filename, pagesize=(page_w, page_h), **kw)
        self.page_w = page_w
        self.page_h = page_h
        self.is_vertical = is_vertical
        
        content_w = page_w - gutter - outer
        content_h = page_h - top - bottom
        
        if not is_vertical:
            # 横書き（左開き）
            # 奇数ページ（右側）: 左がノド(gutter), 右が小口(outer)
            odd_frame = Frame(gutter, bottom, content_w, content_h, id='odd_frame',
                              leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
            # 偶数ページ（左側）: 左が小口(outer), 右がノド(gutter)
            even_frame = Frame(outer, bottom, content_w, content_h, id='even_frame',
                               leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        else:
            # 縦書き（右開き）
            odd_frame = Frame(outer, bottom, content_w, content_h, id='odd_frame',
                              leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
            even_frame = Frame(gutter, bottom, content_w, content_h, id='even_frame',
                               leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
            
        title_frame = Frame(outer, bottom, page_w - 2 * outer, content_h, id='title_frame',
                            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        
        self.addPageTemplates([
            PageTemplate(id='Title', frames=[title_frame]),
            PageTemplate(id='Odd', frames=[odd_frame]),
            PageTemplate(id='Even', frames=[even_frame]),
        ])

    def handle_pageBegin(self):
        if self.page == 1:
            self.pageTemplate = self.pageTemplates[0]  # Title
        elif self.page % 2 == 1:
            self.pageTemplate = self.pageTemplates[1]  # Odd
        else:
            self.pageTemplate = self.pageTemplates[2]  # Even
        super().handle_pageBegin()

def escape_for_paragraph(text: str) -> str:
    """ReportLab Paragraph用のXMLエスケープ"""
    return saxutils.escape(text)

def create_paperback_pdf(
    title: str,
    author: str,
    chapters: List[ChapterSection],
    trim_key: str = "shiroku",
    custom_width_mm: float = 127.0,
    custom_height_mm: float = 188.0,
    is_vertical: bool = False,
    font_style: str = "ipaex_mincho",
    body_font_size: float = 9.5,
    line_spacing_ratio: float = 1.65,
    subtitle: str = "",
    publisher: str = ""
) -> Tuple[bytes, int]:
    """
    ペーパーバック用本文PDFを商業出版クオリティで生成し、(pdf_bytes, 総ページ数) を返す
    - 著者名の前の「著：」は付与せず、入力された形式をそのまま配置
    - 著者名の下に出版社名を配置
    - JIS X 4051準拠の禁則処理と文字間均等割り付けによる美しい両端揃え
    """
    if trim_key == "custom":
        page_width = custom_width_mm * mm
        page_height = custom_height_mm * mm
    else:
        info = TRIM_SIZES.get(trim_key, TRIM_SIZES["shiroku"])
        page_width = info["width_mm"] * mm
        page_height = info["height_mm"] * mm
        
    style_info = FONT_STYLES.get(font_style, FONT_STYLES["ipaex_mincho"])
    target_body = style_info["body_font"]
    target_heading = style_info["heading_font"]
    
    # 登録確認（未登録なら安全に平成フォントへフォールバック）
    registered = pdfmetrics.getRegisteredFontNames()
    body_font = target_body if target_body in registered else "HeiseiMin-W3"
    heading_font = target_heading if target_heading in registered else "HeiseiKakuGo-W5"
    
    leading = body_font_size * line_spacing_ratio
    
    # スタイル定義
    styles = {
        "title": ParagraphStyle(
            "DocTitle",
            fontName=heading_font,
            fontSize=min(24.0, max(18.0, body_font_size * 2.2)),
            leading=min(32.0, max(24.0, body_font_size * 2.2 * 1.35)),
            alignment=TA_CENTER,
            spaceAfter=8 * mm
        ),
        "subtitle": ParagraphStyle(
            "DocSubtitle",
            fontName=body_font,
            fontSize=max(10.5, body_font_size * 1.15),
            leading=max(15.0, body_font_size * 1.15 * 1.4),
            alignment=TA_CENTER,
            spaceAfter=14 * mm
        ),
        "author": ParagraphStyle(
            "DocAuthor",
            fontName=body_font,
            fontSize=max(11.0, body_font_size * 1.25),
            leading=max(16.0, body_font_size * 1.25 * 1.4),
            alignment=TA_CENTER,
            spaceAfter=10 * mm
        ),
        "publisher": ParagraphStyle(
            "DocPublisher",
            fontName=body_font,
            fontSize=max(9.5, body_font_size * 1.05),
            leading=max(14.0, body_font_size * 1.05 * 1.4),
            alignment=TA_CENTER
        ),
        "h1": ParagraphStyle(
            "ChapterHeading1",
            fontName=heading_font,
            fontSize=min(18.0, body_font_size * 1.55),
            leading=min(24.0, body_font_size * 1.55 * 1.35),
            spaceBefore=5 * mm,
            spaceAfter=3 * mm,
            keepWithNext=True
        ),
        "h2": ParagraphStyle(
            "SectionHeading2",
            fontName=heading_font,
            fontSize=min(13.5, body_font_size * 1.25),
            leading=min(18.0, body_font_size * 1.25 * 1.35),
            spaceBefore=6 * mm,
            spaceAfter=2.5 * mm,
            keepWithNext=True
        ),
        "h3": ParagraphStyle(
            "SectionHeading3",
            fontName=heading_font,
            fontSize=min(11.0, body_font_size * 1.1),
            leading=min(15.0, body_font_size * 1.1 * 1.35),
            spaceBefore=4 * mm,
            spaceAfter=2 * mm,
            keepWithNext=True
        ),
        "body": ParagraphStyle(
            "JapaneseBody",
            fontName=body_font,
            fontSize=body_font_size,
            leading=leading,
            alignment=TA_JUSTIFY,
            wordWrap="CJK",
            firstLineIndent=body_font_size,  # 段落頭の全角1文字字下げ
            spaceAfter=0
        ),
        "body_noindent": ParagraphStyle(
            "JapaneseBodyNoIndent",
            fontName=body_font,
            fontSize=body_font_size,
            leading=leading,
            alignment=TA_JUSTIFY,
            wordWrap="CJK",
            firstLineIndent=0,
            spaceAfter=0
        )
    }
    
    buffer = io.BytesIO()
    doc = BookDocTemplate(
        buffer,
        page_width,
        page_height,
        is_vertical=is_vertical,
        gutter=17 * mm,
        outer=13 * mm,
        top=17 * mm,
        bottom=17 * mm
    )
    
    story = []
    
    # 1. 扉ページ（1ページ目）
    story.append(Spacer(1, page_height * 0.20))
    story.append(Paragraph(escape_for_paragraph(title), styles["title"]))
    if subtitle:
        story.append(Paragraph(escape_for_paragraph(subtitle), styles["subtitle"]))
    else:
        story.append(Spacer(1, 8 * mm))
        
    # 著者名（「著：」は付けずそのまま配置）
    if author:
        story.append(Paragraph(escape_for_paragraph(author), styles["author"]))
        
    # 出版社名（著者名の下に配置）
    if publisher:
        story.append(Paragraph(escape_for_paragraph(publisher), styles["publisher"]))
        
    story.append(PageBreak())
    
    # 2. 各章
    for ch_idx, ch in enumerate(chapters):
        # 冒頭の「扉」と重複するタイトルは本文側ではスキップ
        if ch.title.startswith("扉（") and ch_idx == 0:
            continue
            
        # 章見出し
        story.append(Paragraph(escape_for_paragraph(ch.title), styles["h1"]))
        # 見出し下のアクセント罫線
        content_width = page_width - (17 * mm + 13 * mm)
        story.append(HRFlowable(
            width=content_width,
            thickness=0.8,
            color=colors.HexColor("#777777"),
            spaceBefore=1 * mm,
            spaceAfter=5 * mm
        ))
        
        # 本文パラグラフ
        lines = ch.content.split("\n")
        for line in lines:
            stripped = line.strip()
            if not stripped:
                story.append(Spacer(1, leading * 0.45))
                continue
                
            if stripped.startswith("## "):
                h2_text = stripped[3:].strip()
                story.append(Paragraph(escape_for_paragraph(h2_text), styles["h2"]))
                continue
            elif stripped.startswith("### "):
                h3_text = stripped[4:].strip()
                story.append(Paragraph(escape_for_paragraph(h3_text), styles["h3"]))
                continue
            elif stripped.startswith("# "):
                h1_text = stripped[2:].strip()
                story.append(Paragraph(escape_for_paragraph(h1_text), styles["h1"]))
                continue
                
            # 通常の本文段落（全角スペース等ですでに字下げされている場合は二重字下げを防ぐ）
            if stripped.startswith("　") or stripped.startswith(" "):
                p_text = stripped.lstrip("　 ")
                story.append(Paragraph(escape_for_paragraph(p_text), styles["body"]))
            else:
                story.append(Paragraph(escape_for_paragraph(stripped), styles["body"]))
                
        # 章末改ページ（最終章以外）
        if ch_idx < len(chapters) - 1:
            story.append(PageBreak())
            
    # キャンバス生成ファクトリ
    def canvas_maker(*args, **kwargs):
        return NumberedCanvas(
            *args,
            is_vertical=is_vertical,
            header_font=heading_font,
            book_title=title,
            **kwargs
        )
        
    doc.build(story, canvasmaker=canvas_maker)
    
    total_pages = doc.page
    pdf_bytes = buffer.getvalue()
    return pdf_bytes, total_pages
