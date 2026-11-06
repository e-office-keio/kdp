"""
Gemini API を活用した KDP AI アシスタントモジュール
- 本の内容を踏まえた画像生成AIプロンプトの自動考案
- Imagen 3 による高品質な表紙アートワークの直接生成
- KDP用商品説明（使用可能HTMLタグ付）の自動生成
- Amazon検索用 7つのキーワード選定
- 裏表紙あらすじの自動要約
"""
import os
import io
from typing import Dict, List, Optional, Tuple
from PIL import Image
from google import genai
from google.genai import types

def get_genai_client(api_key: Optional[str] = None) -> Optional[genai.Client]:
    """Gemini Clientの初期化"""
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    try:
        return genai.Client(api_key=key)
    except Exception:
        return None

def generate_cover_prompt_idea(
    title: str,
    subtitle: str,
    table_of_contents: str,
    sample_text: str,
    visual_style: str = "cinematic",
    api_key: Optional[str] = None
) -> str:
    """本の内容を深く分析し、表紙に最適な画像生成プロンプト（英語）を作成"""
    client = get_genai_client(api_key)
    
    style_descriptions = {
        "cinematic": "cinematic lighting, elegant, dramatic atmosphere, high detail, award-winning book cover art",
        "minimalist": "minimalist graphic design, clean lines, conceptual art, subtle metaphorical symbolism, modern aesthetics",
        "watercolor": "delicate watercolor painting, artistic brush strokes, soft pastel colors, literary fiction feel",
        "anime_illust": "high quality Japanese anime light novel illustration, vibrant colors, expressive aesthetic",
        "business_tech": "futuristic, sleek corporate technology, glowing geometric patterns, professional non-fiction",
        "vintage": "classic retro vintage book illustration, nostalgic paper texture, classic typography companion"
    }
    style_hint = style_descriptions.get(visual_style, style_descriptions["cinematic"])
    
    fallback_prompt = (
        f"A compelling book cover artwork for a book titled '{title}'. "
        f"Symbolic and metaphorical representation of the book's core themes. "
        f"{style_hint}, no text, no letters, no typography, clean composition."
    )
    
    if not client:
        return fallback_prompt
        
    prompt = f"""あなたは世界的ベストセラーを手がけるブックデザイナー・アートディレクターです。
以下の書籍のタイトル、目次、内容を分析し、**書籍の核心テーマを象徴する、読者が思わず手に取りたくなる最高の一枚絵（表紙イラスト）を描くための画像生成AI用プロンプト（英語）**を作成してください。

【書籍タイトル】{title}
【サブタイトル】{subtitle}
【目次・構成】
{table_of_contents}
【内容サンプル】
{sample_text[:1500]}
【希望するビジュアルスタイル】
{style_hint}

【絶対ルール】
1. 画像内に「文字、タイトル、英字、タイポグラフィ、文字化けしたロゴ」を絶対に描かせないための指示（"no text, no letters, no words, clean background for typography"）を必ず含めてください。
2. 表紙の中央〜背景に配置しやすい、構図の美しいプロンプトにしてください。
3. 出力は、画像生成AIに入力するための英語プロンプトのみ（1〜3文程度）を出力してください。余計な挨拶や解説は不要です。
"""
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text.strip().replace('"', '')
    except Exception:
        return fallback_prompt

def generate_cover_artwork_image(
    prompt: str,
    api_key: Optional[str] = None
) -> Tuple[Optional[Image.Image], str]:
    """Imagen 3 を呼び出して表紙用アートワーク画像を生成"""
    client = get_genai_client(api_key)
    if not client:
        return None, "Gemini APIキーが設定されていません。サイドバーからAPIキーを入力してください。"
        
    try:
        result = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=prompt,
            config=dict(
                number_of_images=1,
                aspect_ratio="3:4",  # 書籍表紙に最適な縦長比率
                output_mime_type="image/jpeg",
            )
        )
        if result.generated_images:
            image_bytes = result.generated_images[0].image.image_bytes
            img = Image.open(io.BytesIO(image_bytes))
            return img, "success"
        else:
            return None, "画像の生成結果が空でした。"
    except Exception as e:
        err_msg = str(e)
        if "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower():
            return None, "画像生成APIの利用上限（クォータ）に達しました。少し待ってから再試行するか、プロンプトをコピーして他の画像生成AI（Midjourney等）をご利用ください。"
        return None, f"画像生成中にエラーが発生しました: {err_msg}"

def generate_kdp_description(
    title: str,
    table_of_contents: str,
    sample_text: str,
    api_key: Optional[str] = None
) -> str:
    """KDP用商品説明文（HTML対応）を生成"""
    client = get_genai_client(api_key)
    
    prompt = f"""あなたはAmazon KDP（Kindle出版）でベストセラーを多数手がけるプロの編集者・マーケターです。
以下の書籍情報をもとに、読者の購買意欲を最大限に刺激する「Amazon KDP用の商品説明文（紹介文）」を作成してください。

【書籍タイトル】{title}
【目次・構成】
{table_of_contents}
【本文サンプル・概要】
{sample_text[:2000]}

【要件・出力ルール】
1. Amazon KDPで許可されているHTMLタグ（<h2>, <b>, <i>, <ul>, <li>, <p>, <br>）のみを使用してください。
2. 以下の構成で書いてください：
   - 冒頭：読者の課題や悩みを惹きつける強烈なキャッチコピー（<h2>タグ）
   - 導入：本書が解決できること、読むメリット
   - 本書の特徴（<b>タグや<ul><li>箇条書きを活用）
   - こんな人におすすめ（チェックリスト形式）
   - 主な目次抜粋
   - 結び：読者の背中を押す購入促進メッセージ
3. Markdownコードブロック（```html ... ```）は付けず、生のHTMLテキストのみを出力してください。
"""
    if not client:
        return f"""<h2>【今すぐ読みたい！】{title}</h2>
<p><b>あなたの日常や学びを次のステージへ引き上げる必読の一冊！</b></p>
<p>本書は、実践的な知見と体系的な解説を通じて、読者が直面する疑問や課題をクリアにするために執筆されました。</p>
<br>
<h2>■ 本書で学べること</h2>
<ul>
  <li><b>本質を掴む基礎理論：</b> 初心者から実践者まで納得のわかりやすい解説</li>
  <li><b>実践的なアクションプラン：</b> 明日からすぐに行動できる具体的なステップ</li>
  <li><b>豊富な事例と考察：</b> 現場で役立つリアルなヒントが満載</li>
</ul>
<br>
<h2>■ こんな方におすすめです</h2>
<ul>
  <li>最新の知見を短時間で効率よくインプットしたい方</li>
  <li>実践に活かせる確かな指針を手に入れたい方</li>
  <li>わかりやすく体系化された良書をお探しの方</li>
</ul>
<br>
<p><b>【今すぐ「購入する」または「Kindle Unlimitedで読む」ボタンを押して、最初の一歩を踏み出しましょう！】</b></p>"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        return f"<!-- 生成中にエラーが発生しました: {e} -->\n" + f"<p><b>{title}</b>の紹介文です。</p>"

def generate_kdp_keywords(
    title: str,
    description: str,
    api_key: Optional[str] = None
) -> List[str]:
    """Amazon KDPの7つの検索キーワードを提案"""
    client = get_genai_client(api_key)
    if not client:
        return [
            f"{title} 入門",
            "Kindle 出版 活用法",
            "ビジネス 実践 ガイド",
            "スキルアップ おすすめ",
            "解説 わかりやすい",
            "最新 トレンド 対策",
            "実践 応用 テキスト"
        ]
        
    prompt = f"""Amazon KDP（Kindle Direct Publishing）では、本の登録時に「7つの検索キーワード」を設定できます。
以下の書籍情報をもとに、読者がAmazon検索バーで実際に検索しそうな、効果的で購買意欲の高い複合検索キーワードをちょうど7個提案してください。

【タイトル】{title}
【内容】{description[:1000]}

【ルール】
- 1行につき1つのキーワード（単語の組み合わせ：例「社会心理学 入門 テキスト」）
- 1〜7番まで、番号はつけずキーワードのみを改行区切りで7行出力してください。
"""
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        lines = [line.strip().lstrip("1234567890.- ") for line in response.text.strip().splitlines() if line.strip()]
        return lines[:7]
    except Exception:
        return [f"{title} 入門", "解説本", "実践ガイド", "最新版", "教養", "テキスト", "必読"]

def generate_back_cover_blurb(
    title: str,
    content: str,
    api_key: Optional[str] = None
) -> str:
    """ペーパーバック裏表紙用の短縮あらすじ（150〜200文字程度）"""
    client = get_genai_client(api_key)
    if not client:
        return f"本書『{title}』は、確かな理論と実践的アプローチを結集した一冊です。日々の学びや実践に新たな視点をもたらし、読者の知的好奇心と行動を力強く後押しします。"
        
    prompt = f"""以下の書籍について、紙書籍（ペーパーバック）の「裏表紙」に掲載する、読者の興味を惹く洗練されたあらすじ・推薦文を作成してください。
文字数は150文字〜200文字程度に収めてください。

【タイトル】{title}
【本文内容抜粋】{content[:2000]}
"""
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text.strip()
    except Exception:
        return f"本書『{title}』は、確かな理論と実践的アプローチを結集した一冊です。"
