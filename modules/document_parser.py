"""
原稿ドキュメント解析モジュール（高度判別版）
Word (.docx), Markdown (.md), テキスト (.txt) の解析と章の構造化
- 既存の静的目次ブロック（ページ番号付き目次）の誤爆防止・スキップ
- 冒頭の「標題紙（書籍名・著者・出版社）」の自動認識
- 前付け（著者紹介、まえがき、序章等）および後付け（あとがき、奥付等）の自動認識
- 節見出し（1. ○○、1-1. ○○等）の階層化
"""
import io
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import docx
from docx.document import Document as DocxDocument

@dataclass
class ChapterSection:
    title: str
    content: str  # Markdownまたはプレーンテキスト
    level: int = 1
    source_filename: str = ""

@dataclass
class ParsedDocument:
    title: str
    chapters: List[ChapterSection] = field(default_factory=list)
    raw_text: str = ""
    author: str = ""
    publisher: str = ""

# 主要な章・セクションの開始パターン
CHAPTER_TITLE_PATTERN = re.compile(
    r"^(第[0-9０-９一二三四五六七八九十百]+章|Chapter\s*[0-9]+|序章|プロローグ|エピローグ|まえがき|はじめに|著者紹介|あとがき|おわりに|奥付|発行日\s*[0-9０-９]+年)\s*(.*)",
    re.IGNORECASE
)

# 目次タイトルのパターン
TOC_HEADER_PATTERN = re.compile(r"^(目\s*次|Contents|TABLE OF CONTENTS)$", re.IGNORECASE)

# 節見出し（H2）のパターン（例: "1. 社会心理学とメディアの共通項", "1-1. ○○"）
SECTION_H2_PATTERN = re.compile(r"^([0-9０-９]+[\.．\s\-]+[^\t\n\r]+)$")

# 行末にページ番号らしき表記があるか（例: " 21", "\t45", "... 103"）
PAGE_NUMBER_SUFFIX_PATTERN = re.compile(r"[\t\s\.・…]+[0-9０-９]+$")

def parse_lines_to_chapters(lines: List[str], default_title: str, source_filename: str = "") -> ParsedDocument:
    """テキスト行のリストから、既存目次の誤爆を防ぎつつ章・節を正確に抽出"""
    chapters: List[ChapterSection] = []
    current_title = "扉（標題紙）"
    current_paragraphs: List[str] = []
    
    in_toc_block = False
    first_chapter_found = False
    book_title = default_title
    
    # 本文の先頭数行から書籍タイトル候補を探す
    non_empty_first_lines = [l.strip() for l in lines[:10] if l.strip()]
    if non_empty_first_lines:
        first_candidate = non_empty_first_lines[0]
        # 「第1章」等で始まっていない場合はそれを書籍タイトルとする
        if not CHAPTER_TITLE_PATTERN.match(first_candidate) and not TOC_HEADER_PATTERN.match(first_candidate):
            book_title = first_candidate
            
    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            if current_paragraphs and current_paragraphs[-1] != "":
                current_paragraphs.append("")
            continue
            
        # 1. 既存の目次ブロック（「目　次」「Contents」）の検出
        if TOC_HEADER_PATTERN.match(stripped):
            in_toc_block = True
            # 目次ブロックはEPUBの動的目次と重複するためスキップ
            continue
            
        # 2. 行末にページ番号がある行の判定（目次項目の特徴: "\t21", " 45"）
        has_page_num = bool(PAGE_NUMBER_SUFFIX_PATTERN.search(stripped))
        
        # 目次ブロック内にいる場合
        if in_toc_block:
            # 本編の始まり（ページ番号を持たない「序章」「第1章」「まえがき」等）が来たら目次ブロック終了
            match_ch = CHAPTER_TITLE_PATTERN.match(stripped)
            if match_ch and not has_page_num:
                in_toc_block = False
            else:
                continue  # 目次行はスキップ
                
        # 3. 章見出し（H1）の判定
        is_md_h1 = stripped.startswith("# ") and not stripped.startswith("## ")
        match_ch = CHAPTER_TITLE_PATTERN.match(stripped)
        
        is_real_chapter_start = False
        detected_chapter_title = ""
        
        if is_md_h1:
            is_real_chapter_start = True
            detected_chapter_title = stripped[2:].strip()
        elif match_ch and not has_page_num:
            if len(stripped) <= 50:
                is_real_chapter_start = True
                detected_chapter_title = stripped
                
        if is_real_chapter_start:
            # 直前までのセクションを保存
            if current_paragraphs:
                content_text = "\n".join(current_paragraphs).strip()
                # 冒頭の扉ページで、内容がタイトルそのものの重複なら整理
                if content_text:
                    chapters.append(ChapterSection(
                        title=current_title,
                        content=content_text,
                        level=1,
                        source_filename=source_filename
                    ))
                current_paragraphs = []
                
            current_title = detected_chapter_title
            first_chapter_found = True
            continue
            
        # 4. 節見出し（## / H2）の判定
        is_md_h2 = stripped.startswith("## ") and not stripped.startswith("### ")
        match_sec = SECTION_H2_PATTERN.match(stripped)
        
        if is_md_h2:
            current_paragraphs.append(stripped)
        elif match_sec and not has_page_num and len(stripped) <= 40:
            current_paragraphs.append(f"## {stripped}")
        else:
            current_paragraphs.append(stripped)
            
    # 最後の章を保存
    if current_paragraphs:
        content_text = "\n".join(current_paragraphs).strip()
        if content_text:
            chapters.append(ChapterSection(
                title=current_title,
                content=content_text,
                level=1,
                source_filename=source_filename
            ))
            
    # 冒頭の「扉（標題紙）」が単なる書籍タイトルと著者名の羅列で、かつ後ろに「まえがき」「第1章」等がある場合、
    # 最初の章のタイトルを書籍タイトルに合わせる
    if chapters and chapters[0].title == "扉（標題紙）":
        if len(chapters) > 1:
            chapters[0].title = f"扉（{book_title}）"
            
    if not chapters:
        chapters.append(ChapterSection(
            title=book_title,
            content="\n".join(lines).strip(),
            level=1,
            source_filename=source_filename
        ))
        
    # 著者名・出版社名の自動抽出（扉や奥付から）
    author_candidate = ""
    publisher_candidate = ""
    full_text = "\n".join(lines)
    
    # 1. 奥付からの抽出
    m_author = re.search(r"(?:著者|著者名)[\s\u3000:：]+([^\n\r]+)", full_text)
    if m_author:
        author_candidate = m_author.group(1).strip()
    m_pub = re.search(r"(?:発行所|出版社|発行元)[\s\u3000:：]+([^\n\r]+)", full_text)
    if m_pub:
        publisher_candidate = m_pub.group(1).strip()
        
    # 2. 扉（冒頭セクション）からの抽出フォールバック
    if chapters and chapters[0].content:
        title_lines = [l.strip() for l in chapters[0].content.split("\n") if l.strip()]
        if len(title_lines) >= 2 and not author_candidate:
            # 2行目が著者らしき場合（タイトルと異なり、かつ短めの文字列）
            cand = title_lines[1]
            if len(cand) <= 25 and not CHAPTER_TITLE_PATTERN.match(cand):
                author_candidate = cand
        if len(title_lines) >= 3 and not publisher_candidate:
            cand = title_lines[2]
            if len(cand) <= 25:
                publisher_candidate = cand

    return ParsedDocument(
        title=book_title,
        chapters=chapters,
        raw_text=full_text,
        author=author_candidate,
        publisher=publisher_candidate
    )

def parse_docx_bytes(file_bytes: bytes, filename: str) -> ParsedDocument:
    """Word (.docx) のバイトデータから構造化テキストを抽出"""
    f = io.BytesIO(file_bytes)
    doc: DocxDocument = docx.Document(f)
    lines: List[str] = []
    
    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            lines.append("")
            continue
        style_name = (p.style.name or "").lower()
        if "heading 1" in style_name or "見出し 1" in style_name:
            lines.append(f"# {text}")
        elif "heading 2" in style_name or "見出し 2" in style_name:
            lines.append(f"## {text}")
        elif "heading 3" in style_name or "見出し 3" in style_name:
            lines.append(f"### {text}")
        else:
            lines.append(text)
            
    base_title = os.path.splitext(filename)[0]
    return parse_lines_to_chapters(lines, base_title, filename)

def parse_markdown_text(text: str, filename: str) -> ParsedDocument:
    """Markdown / プレーンテキストから章を解析"""
    lines = text.splitlines()
    base_title = os.path.splitext(filename)[0]
    return parse_lines_to_chapters(lines, base_title, filename)

def merge_documents(docs: List[ParsedDocument], book_title: str) -> ParsedDocument:
    """複数ドキュメントを並び順通りに単一ドキュメントに結合"""
    all_chapters: List[ChapterSection] = []
    combined_raw: List[str] = []
    
    for doc in docs:
        for ch in doc.chapters:
            all_chapters.append(ch)
            combined_raw.append(f"# {ch.title}\n\n{ch.content}")
            
    return ParsedDocument(
        title=book_title,
        chapters=all_chapters,
        raw_text="\n\n".join(combined_raw)
    )
