# TODO: define a Settings class (pydantic-settings) that loads DATABASE_URL,
# JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES, GEMINI_API_KEY, and RESEND_API_KEY
# from a local .env file. DATABASE_URL uses the postgresql+asyncpg:// scheme.

from pydantic_settings import BaseSettings

# class Settings(BaseSettings): ...
