from fastapi import Request
from slowapi import Limiter
from backend.app.core.config import settings

def get_client_ip(request: Request) -> str:
    """
    Extract client IP, respecting X-Forwarded-For if request comes from
    a trusted reverse-proxy in settings.FORWARDED_ALLOW_IPS.
    """
    direct_ip = request.client.host if request.client and request.client.host else "127.0.0.1"
    if direct_ip in settings.FORWARDED_ALLOW_IPS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
            if client_ip:
                return client_ip
    return direct_ip

limiter = Limiter(key_func=get_client_ip)
