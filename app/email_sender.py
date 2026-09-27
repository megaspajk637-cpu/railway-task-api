"""Отправка кода подтверждения через Resend (HTTPS API)."""
import os

import resend
from resend.exceptions import ResendError

resend.api_key = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "onboarding@resend.dev")
FROM_NAME = os.getenv("FROM_NAME", "User Site")


def send_verification_code(to_email: str, code: str) -> bool:
    """Отправляет код через Resend. В dev-режиме печатает код в логи."""
    if not resend.api_key:
        print(f"[DEV] Код для {to_email}: {code}")
        return True

    params: resend.Emails.SendParams = {
        "from": f"{FROM_NAME} <{FROM_EMAIL}>",
        "to": [to_email],
        "subject": "Подтверждение email",
        "html": f"""
        <div style="font-family:sans-serif;max-width:480px;margin:auto;padding:24px;">
          <h2 style="color:#111827;">Подтвердите email</h2>
          <p style="color:#374151;">Ваш код подтверждения:</p>
          <p style="font-size:32px;font-weight:bold;letter-spacing:8px;
                    background:#f3f4f6;padding:16px;border-radius:8px;
                    text-align:center;color:#111827;">{code}</p>
          <p style="color:#6b7280;font-size:14px;">Код действует 10 минут.</p>
        </div>
        """,
    }

    try:
        resend.Emails.send(params)
        return True
    except ResendError as e:
        print(f"[Resend error] {e}")
        return False
    except Exception as e:
        print(f"[Email error] {type(e).__name__}: {e}")
        return False