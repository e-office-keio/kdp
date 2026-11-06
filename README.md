# KDP Publisher Studio 📚

Amazon Kindle Direct Publishing (KDP) の電子書籍およびペーパーバック（紙書籍）出版を自動化・支援する Web アプリケーションです。Streamlit 上で動作し、Streamlit Community Cloud に無料でデプロイできます。

---

## ✨ 主な機能

1. **原稿のアップロード＆章の並べ替え・結合**
   - Word (`.docx`)、Markdown (`.md`)、テキスト (`.txt`) の複数ファイル一括アップロード
   - ドラッグ＆ドロップ感覚でボタンによる章の順番入れ替え・プレビュー
   - 単一の書籍原稿に自動マージ

2. **日本語表記の自動整形・校正**
   - 三点リーダー（`...` → `……`）やダッシュ（`--` → `――`）の統一
   - 感嘆符・疑問符（！？）直後の全角スペース自動挿入
   - 段落先頭の全角字下げ、引用符の正規化

3. **電子書籍（EPUB 3.0）書き出し**
   - **横書き（左開き）** / **縦書き（右開き）** のワンクリック切り替え
   - KDP推奨リフロー型 XHTML + 目次（Navigation Document & NCX）自動生成
   - 表紙画像の自動埋め込み

4. **ペーパーバック（紙書籍）用 本文PDF組版**
   - **多様な判型プリセット**: 四六判、A5判、B6判、文庫判、新書判、B5判、米判(6×9インチ)、カスタムサイズ(mm指定)
   - KDP推奨のノド側（綴じ代）・小口側マージンを考慮した奇数／偶数ページ自動振り分け
   - ノンブル（ページ番号）および柱（ヘッダー）の自動付与

5. **表紙サイズの精密計算＆画像自動生成**
   - **電子書籍用**: KDP推奨（2,560 × 1,600 px / 1.6:1）の表紙画像を自動描画
   - **ペーパーバック用**: 判型 × ページ数 × 用紙（白/クリーム）から背表紙幅および裁ち落とし（各3.2mm）を含む全体展開図（300 DPI）を精密計算
   - 79ページ以上で背表紙へのタイトル・著者名の印字に対応
   - お手持ちのイラスト・写真のセンタリング合成対応

6. **Gemini AI アシスタント（BYOK: Bring Your Own Key 対応）**
   - **各自のAPIキーで安全に動作**: 利用者が自身のGemini APIキーを画面から入力して使用可能（サーバー側には保存されません）。未入力時も標準テンプレートで動作。
   - **KDP用 商品説明文（HTML）**: Amazonの販売ページで売上を高めるHTML付き紹介文を自動生成
   - **7つの検索キーワード**: KDP登録画面で設定する検索ボリュームの高いキーワードを提案
   - **ペーパーバック裏表紙あらすじ**: 短縮要約（150〜200文字）の作成

---

## 🚀 ローカル環境での起動方法

```bash
cd kdp_publisher_app

# 仮想環境の作成とパッケージインストール (uv の場合)
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt

# アプリの起動
streamlit run app.py
```

ブラウザで `http://localhost:8501` にアクセスすると画面が表示されます。

---

## ☁️ Streamlit Community Cloud での無料公開手順

1. **GitHub にリポジトリを作成**
   この `kdp_publisher_app` フォルダの内容を GitHub の新しいリポジトリにプッシュします。
   ```bash
   cd kdp_publisher_app
   git init
   git add .
   git commit -m "Initial commit for KDP Publisher Studio"
   git branch -M main
   git remote add origin https://github.com/<あなたのユーザー名>/<リポジトリ名>.git
   git push -u origin main
   ```

2. **Streamlit Community Cloud にサインイン**
   - [share.streamlit.io](https://share.streamlit.io/) にアクセスし、GitHub アカウントでログイン。

3. **「New app」からデプロイ**
   - **Repository**: 上記で作成した GitHub リポジトリを選択
   - **Branch**: `main`
   - **Main file path**: `app.py`
   - **Advanced settings (Secrets)** に必要に応じて Gemini API キーを設定:
     ```toml
     GEMINI_API_KEY = "your-api-key-here"
     ```
   - 「Deploy!」をクリックすると数分で全世界に公開されます。
