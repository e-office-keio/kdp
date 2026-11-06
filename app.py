"""
KDP Publisher Studio - Kindle＆ペーパーバック出版自動化 Web アプリ
Streamlit メインアプリケーション
"""
import io
import os
import streamlit as st
from PIL import Image

from modules.document_parser import (
    parse_docx_bytes,
    parse_markdown_text,
    merge_documents,
    ParsedDocument,
    ChapterSection
)
from modules.formatter import format_japanese_text
from modules.epub_generator import create_epub3
from modules.pdf_generator import create_paperback_pdf, FONT_STYLES
from modules.cover_calculator import (
    TRIM_SIZES,
    calculate_paperback_cover,
    get_ebook_cover_dimensions
)
from modules.cover_generator import (
    create_ebook_cover_image,
    create_paperback_cover_image
)
from modules.ai_assistant import (
    generate_kdp_description,
    generate_kdp_keywords,
    generate_back_cover_blurb,
    generate_cover_prompt_idea,
    generate_cover_artwork_image
)

# ページ基本設定
st.set_page_config(
    page_title="KDP Publisher Studio | Kindle出版自動化ツール",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# セッション状態の初期化
if "uploaded_items" not in st.session_state:
    st.session_state.uploaded_items = []  # dict: {"id": str, "name": str, "doc": ParsedDocument}
if "cover_image_bytes" not in st.session_state:
    st.session_state.cover_image_bytes = None
if "center_art_image" not in st.session_state:
    st.session_state.center_art_image = None
if "last_page_count" not in st.session_state:
    st.session_state.last_page_count = 120
if "book_title" not in st.session_state:
    st.session_state.book_title = "メディアと心理学入門"
if "subtitle" not in st.session_state:
    st.session_state.subtitle = "情報化社会を生き抜くための基礎教養"
if "author" not in st.session_state:
    st.session_state.author = "著者名"
if "publisher" not in st.session_state:
    st.session_state.publisher = ""

def handle_uploaded_files():
    """原稿アップロード時のコールバック（ウィジェット描画前に実行され、タイトル・著者・出版社の自動反映が可能）"""
    uploaded = st.session_state.get("manuscript_files_uploader")
    if not uploaded:
        return
    existing_names = [item["name"] for item in st.session_state.uploaded_items]
    for f in uploaded:
        if f.name not in existing_names:
            content_bytes = f.read()
            if f.name.endswith(".docx"):
                parsed = parse_docx_bytes(content_bytes, f.name)
            else:
                text_str = content_bytes.decode("utf-8", errors="ignore")
                parsed = parse_markdown_text(text_str, f.name)
            st.session_state.uploaded_items.append({
                "id": f.name,
                "name": f.name,
                "doc": parsed
            })
            # 原稿からタイトル・著者名・出版社名を自動抽出して反映
            if parsed.title and (st.session_state.book_title == "メディアと心理学入門" or not st.session_state.book_title):
                st.session_state.book_title = parsed.title
            if parsed.author and (st.session_state.author == "著者名" or not st.session_state.author):
                st.session_state.author = parsed.author
            if parsed.publisher and not st.session_state.publisher:
                st.session_state.publisher = parsed.publisher

# ----------------- サイドバー設定 -----------------
with st.sidebar:
    st.title("📚 書籍基本設定")
    
    book_title = st.text_input("書籍タイトル", key="book_title")
    subtitle = st.text_input("サブタイトル（任意）", key="subtitle")
    author = st.text_input("著者名（例：山田太郎 著、鈴木一郎 編著）", key="author")
    publisher = st.text_input("出版社名（任意）", key="publisher", placeholder="〇〇出版 / レーベル名等")
    
    st.divider()
    st.subheader("🖋 組版・レイアウト")
    writing_direction = st.radio(
        "文章の組み方向",
        options=["横書き (左開き)", "縦書き (右開き)"],
        index=0,
        help="横書きは学術書・ビジネス書・解説書におすすめ。縦書きは小説や文芸作品に適しています。"
    )
    is_vertical = "縦書き" in writing_direction
    
    st.divider()
    st.subheader("📖 ペーパーバック判型")
    trim_options = list(TRIM_SIZES.keys()) + ["custom"]
    
    def format_trim_label(k):
        if k == "custom":
            return "カスタムサイズ (mm直接指定)"
        return TRIM_SIZES[k]["name"]
        
    selected_trim = st.selectbox(
        "本の判型 (トリムサイズ)",
        options=trim_options,
        index=0,
        format_func=format_trim_label,
        help="四六判が最も一般的。教科書や専門書ならA5判も人気です。"
    )
    
    custom_w = 127.0
    custom_h = 188.0
    if selected_trim == "custom":
        col_w, col_h = st.columns(2)
        with col_w:
            custom_w = st.number_input("幅 (mm)", value=127.0, min_value=90.0, max_value=250.0, step=1.0)
        with col_h:
            custom_h = st.number_input("高さ (mm)", value=188.0, min_value=120.0, max_value=350.0, step=1.0)
            
    paper_type = st.selectbox(
        "本文用紙の種類",
        options=["white", "cream", "color"],
        format_func=lambda x: {"white": "白用紙 (一般的・ビジネス書)", "cream": "クリーム用紙 (目に優しい・小説向き)", "color": "カラー用紙"}[x]
    )
    
    st.divider()
    st.subheader("🤖 AI機能設定 (Gemini)")
    st.caption("※APIキーはサーバーに保存されず、あなたのブラウザセッション内でのみ安全に使用されます。")
    
    gemini_key = st.text_input(
        "各自の Gemini API キー",
        type="password",
        value="",
        placeholder="AIzaSy...",
        help="Google AI Studioで無料取得できるAPIキーを入力してください。"
    )
    
    if gemini_key:
        st.success("🟢 APIキーが入力されています")
    else:
        st.info("ℹ️ 未入力の場合でも標準テンプレートで出力できます。")
        st.markdown("[👉 Google AI Studio で無料APIキーを取得する](https://aistudio.google.com/app/apikey)")

# ----------------- メインコンテンツヘッダー -----------------
st.header("🚀 KDP Publisher Studio")
st.caption("WordやMarkdownの原稿から、KDP推奨の電子書籍(EPUB)・紙書籍(PDF)・表紙画像・Amazon紹介文を一括作成")

# タブナビゲーション
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "1. 📄 原稿アップロード＆並べ替え",
    "2. 📱 電子書籍 (EPUB)",
    "3. 📖 ペーパーバック (PDF)",
    "4. 🎨 表紙計算＆自動生成",
    "5. 🤖 AIメタデータ (紹介文・キーワード)"
])

# -------------------------------------------------------------
# タブ1: 原稿アップロード＆並べ替え
# -------------------------------------------------------------
with tab1:
    st.subheader("原稿ファイルのアップロード")
    st.write("章ごとに分かれた複数の Word (`.docx`) や Markdown (`.md`), テキスト (`.txt`) ファイルをドラッグ＆ドロップできます。")
    
    uploaded_files = st.file_uploader(
        "ファイルを選択またはドロップ",
        type=["docx", "md", "txt"],
        accept_multiple_files=True,
        key="manuscript_files_uploader",
        on_change=handle_uploaded_files
    )
                
    st.divider()
    st.subheader("章の順番を並べ替え・確認")
    
    if not st.session_state.uploaded_items:
        st.info("💡 まずは左上から原稿ファイル（.docx または .md）をアップロードしてください。\nサンプルで試したい場合は、以下のボタンでデモ原稿を読み込めます。")
        if st.button("📝 デモ用サンプル章を読み込む"):
            demo1 = parse_markdown_text(
                "# 第1章 メディア心理学とは何か\n\nメディアと人間心理の相互作用は現代社会において極めて重要です……\n\n多くの人々がスマートフォンを手放せない理由とは何でしょうか？\n\n## 1.1 情報の洪水と認知負荷\n\n私たちは日々、膨大な情報に晒されています。",
                "01_第1章.md"
            )
            demo2 = parse_markdown_text(
                "# 第2章 ソーシャルメディアと自己呈示\n\nSNS上の「いいね！」が私たちの自己肯定感に与える影響について考察します。\n\n――承認欲求のメカニズムを解き明かしましょう！\n\n## 2.1 フィルターバブルの罠\n\n自分と似た意見ばかりに囲まれる現象が起きています。",
                "02_第2章.md"
            )
            st.session_state.uploaded_items = [
                {"id": "01_第1章.md", "name": "01_第1章.md", "doc": demo1},
                {"id": "02_第2章.md", "name": "02_第2章.md", "doc": demo2}
            ]
            st.rerun()
    else:
        # 並べ替えUI
        items_to_remove = []
        for i, item in enumerate(st.session_state.uploaded_items):
            col_order, col_title, col_up, col_down, col_del = st.columns([1, 6, 1, 1, 1])
            with col_order:
                st.markdown(f"**第 {i+1} 項目**")
            with col_title:
                st.write(f"📁 **{item['name']}** （章数: {len(item['doc'].chapters)} / タイトル: {item['doc'].title}）")
            with col_up:
                if st.button("⬆️", key=f"up_{i}", disabled=(i == 0)):
                    st.session_state.uploaded_items[i], st.session_state.uploaded_items[i-1] = (
                        st.session_state.uploaded_items[i-1], st.session_state.uploaded_items[i]
                    )
                    st.rerun()
            with col_down:
                if st.button("⬇️", key=f"down_{i}", disabled=(i == len(st.session_state.uploaded_items) - 1)):
                    st.session_state.uploaded_items[i], st.session_state.uploaded_items[i+1] = (
                        st.session_state.uploaded_items[i+1], st.session_state.uploaded_items[i]
                    )
                    st.rerun()
            with col_del:
                if st.button("🗑️", key=f"del_{i}"):
                    items_to_remove.append(i)
                    
        if items_to_remove:
            for idx in reversed(items_to_remove):
                st.session_state.uploaded_items.pop(idx)
            st.rerun()
            
        if st.button("全ファイルをクリア", type="secondary"):
            st.session_state.uploaded_items = []
            st.rerun()
            
    # 日本語自動整形設定
    st.divider()
    st.subheader("⚙️ 日本語自動整形・組版ルール")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        opt_ellipsis = st.checkbox("三点リーダーの統一（... → ……）", value=True)
        opt_dash = st.checkbox("ダッシュの統一（-- → ――）", value=True)
        opt_exclamation = st.checkbox("感嘆符・疑問符後の全角空き自動挿入（！？＋全角）", value=True)
    with col_f2:
        opt_indent = st.checkbox("段落頭の字下げ自動補完（全角スペース）", value=True)
        opt_normalize_q = st.checkbox("引用符・かぎ括弧の統一", value=True)

# 統合原稿の生成関数
def get_current_merged_doc() -> ParsedDocument:
    raw_docs = [it["doc"] for it in st.session_state.uploaded_items]
    merged = merge_documents(raw_docs, book_title)
    
    # 整形適用
    formatted_chapters = []
    for ch in merged.chapters:
        formatted_content = format_japanese_text(
            ch.content,
            fix_ellipsis=opt_ellipsis,
            fix_dash=opt_dash,
            fix_exclamation_space=opt_exclamation,
            indent_paragraphs=opt_indent,
            normalize_quotes=opt_normalize_q,
            is_vertical=is_vertical
        )
        formatted_chapters.append(ChapterSection(
            title=ch.title,
            content=formatted_content,
            level=ch.level,
            source_filename=ch.source_filename
        ))
    merged.chapters = formatted_chapters
    return merged

# -------------------------------------------------------------
# タブ2: 電子書籍 (EPUB) 出力
# -------------------------------------------------------------
with tab2:
    st.subheader("📱 Kindle電子書籍 (EPUB 3.0) の生成")
    st.write(f"現在の設定: **{writing_direction}** / タイトル: **{book_title}** / 著者: **{author}**")
    
    if not st.session_state.uploaded_items:
        st.warning("⚠️ 原稿ファイルがありません。タブ1からファイルをアップロードしてください。")
    else:
        merged_doc = get_current_merged_doc()
        
        st.success(f"合計 {len(merged_doc.chapters)} 章の原稿がスタンバイされています。")
        
        with st.expander("📖 目次と章構成プレビュー"):
            for idx, ch in enumerate(merged_doc.chapters, 1):
                st.markdown(f"**{idx}. {ch.title}**")
                st.caption(f"文字数: 約{len(ch.content)}字")
                
        # 表紙画像をつけるかどうか
        use_cover_in_epub = st.checkbox("生成された表紙画像（または手持ち画像）をEPUBに埋め込む", value=True)
        
        epub_cover_bytes = st.session_state.cover_image_bytes if use_cover_in_epub else None
        
        if st.button("✨ KDP用 EPUB を書き出す", type="primary"):
            with st.spinner("EPUB 3.0 ファイルをパッケージング中..."):
                epub_data = create_epub3(
                    title=book_title,
                    author=author,
                    chapters=merged_doc.chapters,
                    is_vertical=is_vertical,
                    cover_image_bytes=epub_cover_bytes,
                    cover_image_ext="jpg"
                )
                
            st.balloons()
            st.success("✅ EPUBの生成が完了しました！以下のボタンからダウンロードできます。")
            st.download_button(
                label=f"📥 {book_title}.epub をダウンロード",
                data=epub_data,
                file_name=f"{book_title}.epub",
                mime="application/epub+zip"
            )

# -------------------------------------------------------------
# タブ3: ペーパーバック (PDF) 出力
# -------------------------------------------------------------
with tab3:
    st.subheader("📖 ペーパーバック（紙書籍）用 本文PDF の組版設定")
    
    trim_desc = TRIM_SIZES[selected_trim]["name"] if selected_trim != "custom" else f"カスタム ({custom_w}×{custom_h}mm)"
    st.info(f"選択判型: **{trim_desc}** | 組版: **{writing_direction}** | 用紙: **{paper_type}**")
    
    # --- フォント・レイアウト設定 ---
    st.markdown("#### 🖋️ フォント・文字組みの詳細カスタマイズ")
    col_font_style, col_font_size, col_line_space = st.columns([2, 1, 1])
    
    with col_font_style:
        selected_font_style = st.selectbox(
            "フォントの組み合わせ（書体）",
            options=list(FONT_STYLES.keys()),
            format_func=lambda k: FONT_STYLES[k]["name"],
            help="書籍のジャンルに合わせて適切な書体を選択できます。"
        )
        st.caption(f"💡 {FONT_STYLES[selected_font_style]['desc']}")
        
    with col_font_size:
        body_font_size = st.slider(
            "本文フォントサイズ (pt)",
            min_value=8.0,
            max_value=13.0,
            value=9.5,
            step=0.5,
            help="標準的な文庫・新書は9.0〜9.5pt、単行本は9.5〜10.5pt、大活字本は11.5pt以上が目安です。"
        )
        
    with col_line_space:
        line_spacing_ratio = st.slider(
            "行送りの広さ（行間倍率）",
            min_value=1.4,
            max_value=2.2,
            value=1.65,
            step=0.05,
            help="行送り（1行の高さ）の比率。1.6〜1.75倍が読みやすく疲れにくい書籍の黄金比です。"
        )
        
    # 文字組みの目安表示
    # 選択判型から本文領域幅を計算
    w_mm_calc = custom_w if selected_trim == "custom" else TRIM_SIZES[selected_trim]["width_mm"]
    h_mm_calc = custom_h if selected_trim == "custom" else TRIM_SIZES[selected_trim]["height_mm"]
    body_w_pt = (w_mm_calc - 30.0) * (72.0 / 25.4)
    body_h_pt = (h_mm_calc - 34.0) * (72.0 / 25.4)
    approx_chars_per_line = int(body_w_pt / (body_font_size * 1.05))
    approx_lines_per_page = int(body_h_pt / (body_font_size * line_spacing_ratio))
    
    st.markdown(
        f"""<div style="background-color: #F1F5F9; padding: 10px 16px; border-radius: 8px; margin-bottom: 16px; font-size: 0.9em;">
        📐 <b>この設定での文字組み目安:</b> 1行あたり <b>約 {approx_chars_per_line} 文字</b> × 1ページあたり <b>約 {approx_lines_per_page} 行</b>
        （文字数目安: 1ページあたり 約 {approx_chars_per_line * approx_lines_per_page} 字）
        </div>""",
        unsafe_allow_html=True
    )
    
    st.write("KDP推奨のノド側（綴じ代 17mm）と小口側（13mm）の余白、天・地（各17mm）、ノンブル（ページ番号）が自動付与されます。")
    
    if not st.session_state.uploaded_items:
        st.warning("⚠️ 原稿ファイルがありません。タブ1からファイルをアップロードしてください。")
    else:
        merged_doc = get_current_merged_doc()
        
        col_pdf_btn, col_pdf_info = st.columns([1, 2])
        
        with col_pdf_btn:
            generate_pdf = st.button("📄 印刷用本文PDFを生成", type="primary")
            
        if generate_pdf:
            with st.spinner("ペーパーバック用PDFを組版中..."):
                pdf_data, total_pages = create_paperback_pdf(
                    title=book_title,
                    author=author,
                    chapters=merged_doc.chapters,
                    trim_key=selected_trim,
                    custom_width_mm=custom_w,
                    custom_height_mm=custom_h,
                    is_vertical=is_vertical,
                    font_style=selected_font_style,
                    body_font_size=body_font_size,
                    line_spacing_ratio=line_spacing_ratio,
                    subtitle=subtitle,
                    publisher=publisher
                )
                st.session_state.last_page_count = max(total_pages, 24)
                
            st.success(f"✅ 組版完了！ 総ページ数: **{total_pages} ページ**")
            if total_pages < 24:
                st.warning(f"⚠️ KDPペーパーバックは最低24ページ以上が必要です（現在のページ数: {total_pages}）。")
            elif total_pages < 79:
                st.info("ℹ️ 現在のページ数では背表紙に文字を入れることができません（79ページ以上で背表紙文字入れが推奨されます）。")
            else:
                st.success("🎉 79ページ以上あるため、背表紙にタイトルと著者名を印字できます！")
                
            st.download_button(
                label=f"📥 {book_title}_ペーパーバック本文.pdf をダウンロード",
                data=pdf_data,
                file_name=f"{book_title}_paperback_body.pdf",
                mime="application/pdf"
            )

# -------------------------------------------------------------
# タブ4: 表紙計算＆自動生成
# -------------------------------------------------------------
with tab4:
    st.subheader("🎨 表紙サイズの精密計算＆自動デザイン生成")
    
    # ページ数入力（直近のPDF生成結果を自動反映）
    pages_for_cover = st.number_input(
        "本文総ページ数（背表紙幅の計算に使用）",
        min_value=24,
        max_value=1000,
        value=st.session_state.last_page_count,
        step=2
    )
    
    # 寸法の計算
    dims = calculate_paperback_cover(
        trim_key=selected_trim,
        page_count=pages_for_cover,
        paper_type=paper_type,
        custom_width_mm=custom_w,
        custom_height_mm=custom_h
    )
    
    # 寸法サマリーカード
    col_d1, col_d2, col_d3, col_d4 = st.columns(4)
    with col_d1:
        st.metric("背表紙の厚み (Spine)", f"{dims.spine_width_mm:.2f} mm")
    with col_d2:
        st.metric("全体幅 (裁ち落とし込)", f"{dims.total_width_mm:.2f} mm")
    with col_d3:
        st.metric("全体高さ (裁ち落とし込)", f"{dims.total_height_mm:.2f} mm")
    with col_d4:
        st.metric("印刷推奨解像度 (300DPI)", f"{dims.total_width_px} × {dims.total_height_px} px")
        
    st.divider()
    st.subheader("🎨 本の内容を踏まえたAIアートワーク＆デザイン設定")
    
    # --- 1. AI画像生成セクション ---
    with st.expander("✨ 【AI画像生成】本の内容から表紙イラストを自動生成する", expanded=True):
        st.write("書籍のタイトル・目次・本文をAIが読み解き、テーマにぴったりのプロフェッショナルな一枚絵を生成します。")
        
        col_style, col_gen_btn = st.columns([2, 1])
        with col_style:
            art_style = st.selectbox(
                "ビジュアルスタイル（画風）",
                options=["cinematic", "minimalist", "watercolor", "anime_illust", "business_tech", "vintage"],
                format_func=lambda x: {
                    "cinematic": "🎬 ドラマチック・シネマティック（王道・重厚・陰影）",
                    "minimalist": "📐 ミニマル・洗練グラフィック（現代的・知性・教養）",
                    "watercolor": "🎨 水彩画・文学風（柔らかい・小説・エッセイ）",
                    "anime_illust": "🌸 アニメ・イラスト風（ライトノベル・ポップ・親しみやすさ）",
                    "business_tech": "💻 ビジネス・近未来テクノロジー（IT・データ・専門書）",
                    "vintage": "📜 レトロ・ヴィンテージ（歴史・クラシック・格調）"
                }[x]
            )
            
        with col_gen_btn:
            st.write("") # スペーサー
            st.write("")
            generate_art_clicked = st.button("🪄 AIで表紙アートを生成", type="primary")
            
        if generate_art_clicked:
            merged_for_art = get_current_merged_doc() if st.session_state.uploaded_items else None
            art_toc = "\n".join([f"- {ch.title}" for ch in merged_for_art.chapters]) if (merged_for_art and merged_for_art.chapters) else "- 第1章 基礎\n- 第2章 応用"
            art_sample = merged_for_art.chapters[0].content if (merged_for_art and merged_for_art.chapters) else "現代社会とメディア心理学の相互作用に関する知見。"
            
            with st.spinner("本のテーマを分析し、最適なプロンプトを考案中..."):
                cover_prompt = generate_cover_prompt_idea(
                    title=book_title,
                    subtitle=subtitle,
                    table_of_contents=art_toc,
                    sample_text=art_sample,
                    visual_style=art_style,
                    api_key=gemini_key
                )
                st.session_state["cover_prompt"] = cover_prompt
                
            with st.spinner("Google Imagen 3 で美麗なアートワークを描画中（十数秒かかります）..."):
                gen_img, status = generate_cover_artwork_image(cover_prompt, api_key=gemini_key)
                if gen_img:
                    st.session_state.center_art_image = gen_img
                    st.success("🎉 表紙アートワークの生成に成功しました！表紙に自動セットされました。")
                else:
                    st.warning(f"💡 {status}")
                    
        # プロンプト確認・手動調整
        if "cover_prompt" in st.session_state:
            edited_prompt = st.text_area("生成された英語プロンプト（編集可能）", value=st.session_state["cover_prompt"], height=70)
            if st.button("🔄 このプロンプトで再生成"):
                with st.spinner("画像を再生成中..."):
                    gen_img, status = generate_cover_artwork_image(edited_prompt, api_key=gemini_key)
                    if gen_img:
                        st.session_state.center_art_image = gen_img
                        st.success("🎉 再生成に成功しました！")
                    else:
                        st.error(status)
                        
        st.write("または、お手持ちのイラスト・写真ファイルをアップロードして使用することもできます：")
        art_file = st.file_uploader("手持ちの画像ファイルをアップロード", type=["png", "jpg", "jpeg"])
        if art_file:
            st.session_state.center_art_image = Image.open(art_file)
            st.success("画像をセットしました！")
            
        if st.session_state.center_art_image:
            st.image(st.session_state.center_art_image, caption="現在セットされているアートワーク画像", width=240)

    # --- 2. 表紙レイアウトとカラー設定 ---
    st.markdown("#### 🖋️ 表紙デザインとタイポグラフィのカスタマイズ")
    col_layout, col_c1, col_c2 = st.columns([2, 1, 1])
    with col_layout:
        layout_style = st.selectbox(
            "デザインレイアウト構図",
            options=["full_art", "framed", "minimal"],
            format_func=lambda x: {
                "full_art": "🖼 全面アートワーク型（Kindleベストセラー王道・迫力重視）",
                "framed": "🏛 額縁フレーム型（中央配置・クラシック単行本風）",
                "minimal": "📐 ミニマル装飾型（幾何学フレーム・文字重視）"
            }[x]
        )
    with col_c1:
        theme_bg = st.color_picker("ベーストーン（グラデーション色）", "#1A365D")
    with col_c2:
        accent_color = st.color_picker("文字・飾り色", "#FFFFFF")
        
    col_obi, col_back = st.columns(2)
    with col_obi:
        catchphrase_input = st.text_input(
            "表紙の下部に載せるキャッチコピー帯（オビ）",
            value="【話題沸騰！】情報化社会を生き抜くための実践テキスト",
            help="商業出版の「帯（オビ）」のように、読者の目を引く黄色/ゴールドのキャッチコピーを表紙下部に描画します。"
        )
    with col_back:
        back_desc_input = st.text_area(
            "ペーパーバック裏表紙の紹介文・あらすじ",
            value=f"本書『{book_title}』は、確かな知識と実践的な手法を分かりやすくまとめた一冊です。\n現代を生きるすべての人に新しい発見と学びを提供します。",
            height=70
        )
    
    st.divider()
    col_btn_ebook, col_btn_paper = st.columns(2)
    
    with col_btn_ebook:
        if st.button("📱 電子書籍用 表紙を生成 (2560×1600)", type="primary"):
            ebook_img = create_ebook_cover_image(
                title=book_title,
                subtitle=subtitle,
                author=author,
                catchphrase=catchphrase_input,
                theme_color=theme_bg,
                accent_color=accent_color,
                center_image=st.session_state.center_art_image,
                layout_style=layout_style,
                is_vertical=is_vertical
            )
            # バイト化して保持（EPUB埋め込み用）
            img_buf = io.BytesIO()
            ebook_img.save(img_buf, format="JPEG", quality=95)
            st.session_state.cover_image_bytes = img_buf.getvalue()
            st.image(ebook_img, caption="電子書籍用 表紙プレビュー (2560 × 1600 px)", use_container_width=True)
            
            st.download_button(
                "📥 電子書籍表紙 (JPEG) をダウンロード",
                data=img_buf.getvalue(),
                file_name=f"{book_title}_ebook_cover.jpg",
                mime="image/jpeg"
            )
            
    with col_btn_paper:
        if st.button("📖 ペーパーバック用 展開表紙を生成 (完全サイズ)", type="primary"):
            paper_img = create_paperback_cover_image(
                dims=dims,
                title=book_title,
                subtitle=subtitle,
                author=author,
                back_description=back_desc_input,
                catchphrase=catchphrase_input,
                theme_color=theme_bg,
                accent_color=accent_color,
                center_image=st.session_state.center_art_image,
                layout_style=layout_style,
                is_vertical=is_vertical
            )
            img_buf = io.BytesIO()
            paper_img.save(img_buf, format="PNG")
            st.image(paper_img, caption="ペーパーバック展開表紙プレビュー（左：裏表紙 / 中央：背表紙 / 右：表表紙）", use_container_width=True)
            
            st.download_button(
                "📥 ペーパーバック表紙 (PNG) をダウンロード",
                data=img_buf.getvalue(),
                file_name=f"{book_title}_paperback_full_cover.png",
                mime="image/png"
            )

# -------------------------------------------------------------
# タブ5: AIメタデータ (紹介文・キーワード)
# -------------------------------------------------------------
with tab5:
    st.subheader("🤖 Amazon KDP 販売促進メタデータ生成")
    st.write("Gemini AIを活用して、Amazonの販売ページで売上を高めるHTML付き商品説明や、7つの検索キーワードを自動生成します。")
    
    if not gemini_key:
        st.warning("💡 **各自のGemini APIキーをご利用いただけます**\n\n左側のサイドバー「AI機能設定」に各自のAPIキーを入力すると、原稿内容を反映した高精度のAI生成が行われます（未入力の場合は実用的な標準テンプレートが出力されます）。\nAPIキーは [Google AI Studio (無料)](https://aistudio.google.com/app/apikey) からどなたでも即座に取得できます。")
    
    merged_doc = get_current_merged_doc() if st.session_state.uploaded_items else None
    sample_content = merged_doc.chapters[0].content if (merged_doc and merged_doc.chapters) else "本書はメディアと心理学に関する知見を体系化した本です。"
    toc_str = "\n".join([f"- {ch.title}" for ch in merged_doc.chapters]) if (merged_doc and merged_doc.chapters) else "- 第1章 基礎\n- 第2章 応用"
    
    col_ai1, col_ai2 = st.columns(2)
    
    with col_ai1:
        st.markdown("#### 1. KDP用 商品説明文（HTMLフォーマット）")
        if st.button("✨ 商品説明文をAI生成する"):
            with st.spinner("売れる商品説明文を執筆中..."):
                desc_html = generate_kdp_description(
                    title=book_title,
                    table_of_contents=toc_str,
                    sample_text=sample_content,
                    api_key=gemini_key
                )
                st.session_state["kdp_desc_result"] = desc_html
                
        if "kdp_desc_result" in st.session_state:
            st.markdown("##### プレビュー表示")
            st.markdown(st.session_state["kdp_desc_result"], unsafe_allow_html=True)
            st.markdown("##### コピー用HTMLコード")
            st.code(st.session_state["kdp_desc_result"], language="html")
            
    with col_ai2:
        st.markdown("#### 2. KDP 7つの検索キーワード")
        if st.button("🔍 検索キーワードを自動選定"):
            with st.spinner("検索ボリュームの高いキーワードを分析中..."):
                keywords = generate_kdp_keywords(
                    title=book_title,
                    description=sample_content,
                    api_key=gemini_key
                )
                st.session_state["kdp_keywords_result"] = keywords
                
        if "kdp_keywords_result" in st.session_state:
            st.write("KDP出品ページの「キーワード」欄にそのまま入力できます：")
            for idx, kw in enumerate(st.session_state["kdp_keywords_result"], 1):
                st.text_input(f"キーワード {idx}", value=kw, key=f"kw_{idx}")
                
        st.divider()
        st.markdown("#### 3. ペーパーバック裏表紙用あらすじ")
        if st.button("📝 裏表紙用あらすじ（短縮版）を生成"):
            with st.spinner("魅力的な要約を作成中..."):
                blurb = generate_back_cover_blurb(
                    title=book_title,
                    content=sample_content,
                    api_key=gemini_key
                )
                st.session_state["back_blurb_result"] = blurb
                
        if "back_blurb_result" in st.session_state:
            st.text_area("生成された裏表紙あらすじ", value=st.session_state["back_blurb_result"], height=100)
