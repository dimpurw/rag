from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """
    Proteksi endpoint dengan API key sederhana via header 'X-API-Key'.
    Jika API_KEY tidak diset di .env, autentikasi dinonaktifkan (mode development).
    Untuk production, WAJIB set API_KEY di environment.
    """
    settings = get_settings()

    if not settings.api_key:
        return

    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key tidak valid atau tidak disertakan. Sertakan header 'X-API-Key'.",
        )
