import socket

def send_verification_code(to_email: str, code: str) -> bool:
    """Возвращает True, если письмо ушло. В dev-режиме печатает код в логи."""
    if not SMTP_USER or not SMTP_PASS:
        print(f"[DEV] Код для {to_email}: {code}")
        return True

    # --- Railway: форсим IPv4, иначе Errno 101 Network is unreachable ---
    _orig_getaddrinfo = socket.getaddrinfo
    def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
    socket.getaddrinfo = _ipv4_getaddrinfo
    # --------------------------------------------------------------------

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Подтверждение email"
        msg["From"] = f"{FROM_NAME} <{SMTP_USER}>"
        msg["To"] = to_email

        html = f"""
        <div style="font-family:sans-serif;max-width:480px;margin:auto;padding:24px;">
          <h2 style="color:#111827;">Подтвердите email</h2>
          <p style="color:#374151;">Ваш код подтверждения:</p>
          <p style="font-size:32px;font-weight:bold;letter-spacing:8px;
                    background:#f3f4f6;padding:16px;border-radius:8px;
                    text-align:center;color:#111827;">{code}</p>
          <p style="color:#6b7280;font-size:14px;">Код действует 10 минут.</p>
        </div>
        """
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"[SMTP error] {type(e).__name__}: {e}")
        return False
    finally:
        # Обязательно вернуть оригинал, чтобы не влиять на другие модули
        socket.getaddrinfo = _orig_getaddrinfo