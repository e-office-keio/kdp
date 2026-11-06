"""
KDP準拠 EPUB 3.0 生成モジュール
縦書き（右開き・vertical-rl）および横書き（左開き・horizontal-tb）に対応
"""
import io
import os
import uuid
import zipfile
import markdown
from typing import List, Optional
from xml.sax.saxutils import escape

from modules.document_parser import ChapterSection

def create_epub3(
    title: str,
    author: str,
    chapters: List[ChapterSection],
    is_vertical: bool = False,
    cover_image_bytes: Optional[bytes] = None,
    cover_image_ext: str = "jpg",
    language: str = "ja"
) -> bytes:
    """KDP対応のEPUB 3.0バイナリを生成する"""
    book_id = f"urn:uuid:{uuid.uuid4()}"
    buffer = io.BytesIO()
    
    # EPUB ZIP の作成（mimetypeは無圧縮で最初になければならない）
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        # 1. mimetype (ZIP_STORED: 無圧縮)
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        
        # 2. META-INF/container.xml
        container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>"""
        z.writestr("META-INF/container.xml", container_xml)
        
        # 3. CSS (縦書き / 横書きの分岐)
        if is_vertical:
            css_content = """@charset "UTF-8";
html {
    writing-mode: vertical-rl;
    -webkit-writing-mode: vertical-rl;
    -epub-writing-mode: vertical-rl;
    font-family: "Hiragino Mincho ProN", "ヒラギノ明朝 ProN", "Yu Mincho", "YuMincho", "游明朝", "BIZ UDMincho", "MS Mincho", serif;
    font-size: 100%;
    line-height: 1.85;
    letter-spacing: 0.05em;
}
body {
    margin: 0;
    padding: 4% 3%;
}
h1 {
    font-size: 1.6em;
    font-weight: bold;
    margin-left: 2em;
    margin-right: 1em;
    border-right: 3px solid #666;
    padding-right: 0.4em;
    break-before: page;
}
h2 {
    font-size: 1.3em;
    font-weight: bold;
    margin-left: 1.5em;
    margin-right: 0.8em;
}
h3 {
    font-size: 1.1em;
    font-weight: bold;
    margin-left: 1em;
    margin-right: 0.5em;
}
p {
    margin-top: 0;
    margin-bottom: 0;
    text-indent: 1em;
}
.cover-container {
    text-align: center;
    padding: 0;
    margin: 0;
}
.cover-img {
    max-height: 98vh;
    max-width: 98vw;
}
"""
        else:
            css_content = """@charset "UTF-8";
html {
    writing-mode: horizontal-tb;
    font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Hiragino Kaku Gothic ProN", "Yu Gothic", "游ゴシック", "BIZ UDPGothic", sans-serif;
    font-size: 100%;
    line-height: 1.75;
    letter-spacing: 0.03em;
}
body {
    margin: 0;
    padding: 5% 6%;
}
h1 {
    font-size: 1.6em;
    font-weight: bold;
    margin-top: 1.5em;
    margin-bottom: 0.8em;
    border-bottom: 2px solid #555;
    padding-bottom: 0.3em;
    break-before: page;
}
h2 {
    font-size: 1.3em;
    font-weight: bold;
    margin-top: 1.2em;
    margin-bottom: 0.6em;
    border-left: 4px solid #0066cc;
    padding-left: 0.5em;
}
h3 {
    font-size: 1.1em;
    font-weight: bold;
    margin-top: 1em;
    margin-bottom: 0.4em;
}
p {
    margin-top: 0.6em;
    margin-bottom: 0.6em;
    text-align: justify;
}
.cover-container {
    text-align: center;
    padding: 0;
    margin: 0;
}
.cover-img {
    max-height: 98vh;
    max-width: 98vw;
}
"""
        z.writestr("OEBPS/style.css", css_content)
        
        # 4. 表紙画像の追加（あれば）
        has_cover = cover_image_bytes is not None
        cover_mime = "image/jpeg" if cover_image_ext.lower() in ("jpg", "jpeg") else "image/png"
        if has_cover:
            z.writestr(f"OEBPS/cover.{cover_image_ext}", cover_image_bytes)
            cover_xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{language}">
<head>
    <meta charset="utf-8" />
    <title>Cover</title>
    <link rel="stylesheet" type="text/css" href="style.css" />
</head>
<body class="cover-container">
    <img src="cover.{cover_image_ext}" alt="Cover" class="cover-img" />
</body>
</html>"""
            z.writestr("OEBPS/cover.xhtml", cover_xhtml)
            
        # 5. 各章のXHTML作成
        chapter_manifest = []
        chapter_spine = []
        
        for idx, ch in enumerate(chapters, start=1):
            ch_filename = f"chapter_{idx:02d}.xhtml"
            ch_id = f"chapter_{idx:02d}"
            
            # MarkdownをHTMLに変換
            html_body = markdown.markdown(ch.content, extensions=['extra'])
            
            xhtml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{language}">
<head>
    <meta charset="utf-8" />
    <title>{escape(ch.title)}</title>
    <link rel="stylesheet" type="text/css" href="style.css" />
</head>
<body>
    <h1>{escape(ch.title)}</h1>
    {html_body}
</body>
</html>"""
            z.writestr(f"OEBPS/{ch_filename}", xhtml_content)
            chapter_manifest.append(f'<item id="{ch_id}" href="{ch_filename}" media-type="application/xhtml+xml"/>')
            chapter_spine.append(f'<itemref idref="{ch_id}"/>')
            
        # 6. ナビゲーション文書 (nav.xhtml) - EPUB3目次
        nav_items = []
        for idx, ch in enumerate(chapters, start=1):
            ch_filename = f"chapter_{idx:02d}.xhtml"
            nav_items.append(f'<li><a href="{ch_filename}">{escape(ch.title)}</a></li>')
            
        nav_xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{language}">
<head>
    <meta charset="utf-8" />
    <title>目次</title>
    <link rel="stylesheet" type="text/css" href="style.css" />
</head>
<body>
    <nav epub:type="toc" id="toc">
        <h1>目次</h1>
        <ol>
            {"".join(nav_items)}
        </ol>
    </nav>
</body>
</html>"""
        z.writestr("OEBPS/nav.xhtml", nav_xhtml)
        
        # 7. 後方互換 NCX (toc.ncx)
        ncx_points = []
        for idx, ch in enumerate(chapters, start=1):
            ch_filename = f"chapter_{idx:02d}.xhtml"
            ncx_points.append(f"""
        <navPoint id="navPoint-{idx}" playOrder="{idx}">
            <navLabel><text>{escape(ch.title)}</text></navLabel>
            <content src="{ch_filename}"/>
        </navPoint>""")
            
        toc_ncx = f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
    <head>
        <meta name="dtb:uid" content="{book_id}"/>
        <meta name="dtb:depth" content="1"/>
        <meta name="dtb:totalPageCount" content="0"/>
        <meta name="dtb:maxPageNumber" content="0"/>
    </head>
    <docTitle><text>{escape(title)}</text></docTitle>
    <docAuthor><text>{escape(author)}</text></docAuthor>
    <navMap>
        {"".join(ncx_points)}
    </navMap>
</ncx>"""
        z.writestr("OEBPS/toc.ncx", toc_ncx)
        
        # 8. パッケージファイル (OEBPS/content.opf)
        # 縦書きなら page-progression-direction="rtl"
        # 横書きなら page-progression-direction="ltr"
        progression = "rtl" if is_vertical else "ltr"
        
        manifest_items = [
            '<item id="style" href="style.css" media-type="text/css"/>',
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
            '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
        ]
        
        spine_items = []
        if has_cover:
            manifest_items.append(f'<item id="cover-image" href="cover.{cover_image_ext}" media-type="{cover_mime}" properties="cover-image"/>')
            manifest_items.append('<item id="cover-xhtml" href="cover.xhtml" media-type="application/xhtml+xml"/>')
            spine_items.append('<itemref idref="cover-xhtml"/>')
            
        manifest_items.extend(chapter_manifest)
        spine_items.append('<itemref idref="nav"/>')
        spine_items.extend(chapter_spine)
        
        content_opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="pub-id" xml:lang="{language}" prefix="rendition: http://www.idpf.org/vocab/rendition/#">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:identifier id="pub-id">{book_id}</dc:identifier>
        <dc:title>{escape(title)}</dc:title>
        <dc:creator>{escape(author)}</dc:creator>
        <dc:language>{language}</dc:language>
        <meta property="dcterms:modified">2026-11-05T00:00:00Z</meta>
        {f'<meta name="cover" content="cover-image"/>' if has_cover else ''}
    </metadata>
    <manifest>
        {"".join(manifest_items)}
    </manifest>
    <spine page-progression-direction="{progression}" toc="ncx">
        {"".join(spine_items)}
    </spine>
</package>"""
        z.writestr("OEBPS/content.opf", content_opf)
        
    return buffer.getvalue()
