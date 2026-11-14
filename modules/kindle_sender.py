"""
Send to Kindle 送信モジュール
Kindle専用メールアドレス宛てに電子書籍（EPUB等）をメール添付して送信
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.header import Header
from typing import Tuple, Optional


def send_to_kindle(
    kindle_email: str,
    sender_email: str,
    smtp_password: str,
    file_bytes: bytes,
    file_name: str,
    smtp_host: str = "smtp.gmail.com",
    smtp_port: int = 587,
    use_tls: bool = True,
    subject: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Kindle宛てに電子書籍ファイルをメール添付で送信する

    Args:
        kindle_email: 送信先Kindleアドレス（例: xxxx@kindle.com）
        sender_email: 送信元メールアドレス（Amazonの承認済みアドレスに登録されているもの）
        smtp_password: 送信元メールのSMTPパスワードまたはアプリパスワード
        file_bytes: 添付する書籍データ（EPUBまたはPDF）
        file_name: 添付ファイル名（例: book.epub）
        smtp_host: SMTPサーバーのホスト名（デフォルト: smtp.gmail.com）
        smtp_port: SMTPポート（デフォルト: 587）
        use_tls: STARTTLSを使用するかどうか
        subject: メール件名（省略時はファイル名）

    Returns:
        (success: bool, message: str): 成功成否と結果メッセージ
    """
    if not kindle_email or "@kindle.com" not in kindle_email.lower():
        return False, "有効なKindleメールアドレス（@kindle.com）を入力してください。"
    if not sender_email or "@" not in sender_email:
        return False, "有効な送信元メールアドレスを入力してください。"
    if not smtp_password:
        return False, "送信元のSMTPパスワード（Gmailの場合はアプリパスワード）を入力してください。"
    if not file_bytes:
        return False, "送信する書籍ファイルデータが空です。"

    # メール件名の作成
    email_subject = subject or os.path.splitext(file_name)[0]

    # MIMEメッセージの構築
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = kindle_email
    msg["Subject"] = Header(email_subject, "utf-8").encode()

    # 本文（Send to Kindleは本文なしでも可）
    body_text = f"Send to Kindle: {email_subject}\nAttached file: {file_name}"
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    # ファイル添付
    part = MIMEApplication(file_bytes, Name=file_name)
    # RFC 2231 / ヘッダーエンコーディング
    part.add_header(
        "Content-Disposition",
        "attachment",
        filename=("utf-8", "", file_name)
    )
    msg.attach(part)

    # SMTP送信処理
    try:
        if smtp_port == 465:
            # SSL
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as server:
                server.login(sender_email, smtp_password)
                server.send_message(msg)
        else:
            # STARTTLS (587)
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                server.ehlo()
                if use_tls:
                    server.starttls()
                    server.ehlo()
                server.login(sender_email, smtp_password)
                server.send_message(msg)
        return True, f"Kindle宛て（{kindle_email}）に正常に送信しました！"
    except smtplib.SMTPAuthenticationError:
        return False, (
            "SMTP認証に失敗しました。メールアドレスまたはパスワードをご確認ください。\n"
            "※Gmailをご利用の場合は、通常のパスワードではなくGoogleアカウント設定で発行した「アプリパスワード（16桁）」が必要です。"
        )
    except smtplib.SMTPConnectError:
        return False, f"SMTPサーバー（{smtp_host}:{smtp_port}）への接続に失敗しました。"
    except Exception as e:
        return False, f"送信エラーが発生しました: {str(e)}"
