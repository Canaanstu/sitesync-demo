from pathlib import Path
import secrets
from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    app_env: str = 'development'
    demo_mode: bool = True
    app_url: str = 'http://localhost:3000'
    api_url: str = 'http://localhost:8000'
    database_url: str = 'sqlite:///.local/construction.db'
    redis_url: str = 'redis://localhost:6379/0'
    jwt_secret: str = ''
    token_encryption_key: str = ''
    procore_client_id: str = ''
    procore_client_secret: str = ''
    procore_base_url: str = 'https://api.procore.com'
    procore_login_url: str = 'https://login.procore.com'
    microsoft_client_id: str = ''
    microsoft_client_secret: str = ''
    microsoft_tenant_id: str = 'organizations'
    microsoft_scopes: str = 'openid profile offline_access User.Read Mail.Read Files.Read.All Sites.Read.All'
    enable_email_send: bool = False
    openai_api_key: str = ''
    openai_model: str = 'gpt-4.1-mini'
    openai_embedding_model: str = 'text-embedding-3-small'
    anthropic_api_key: str = ''
    anthropic_model: str = 'claude-sonnet-4-5'
    ai_provider: str = 'openai'
    bootstrap_email: str = ''
    bootstrap_password: str = ''
    # Hosted demos retain fictional data, but never use the published local login.
    private_demo: bool = False
    private_demo_password: str = ''


settings = Settings()
if settings.private_demo:
    if not settings.demo_mode or settings.enable_email_send:
        raise RuntimeError('Private demo hosting requires DEMO_MODE=true and ENABLE_EMAIL_SEND=false.')
    if len(settings.private_demo_password.encode()) < 20 or len(settings.private_demo_password.encode()) > 72 or settings.private_demo_password == 'DemoProject2026!':
        raise RuntimeError('Private hosting requires a unique PRIVATE_DEMO_PASSWORD of 20-72 bytes.')
    if len(settings.jwt_secret) < 32 or not settings.token_encryption_key:
        raise RuntimeError('Private hosting requires explicit signing and encryption secrets.')
    if not settings.app_url.startswith('https://') or not settings.api_url.startswith('https://'):
        raise RuntimeError('Private hosting requires HTTPS URLs.')
if settings.ai_provider not in ('openai', 'anthropic'):
    raise RuntimeError('AI_PROVIDER must be openai or anthropic.')
if not settings.demo_mode and (not settings.jwt_secret or not settings.token_encryption_key):
    raise RuntimeError('Live mode requires explicit JWT_SECRET and TOKEN_ENCRYPTION_KEY shared by all backend services.')
Path('.local').mkdir(exist_ok=True)
if settings.app_env == 'production':
    if settings.demo_mode or len(settings.jwt_secret) < 32 or not settings.token_encryption_key:
        raise RuntimeError('Production requires DEMO_MODE=false and strong JWT/encryption secrets.')
    if not settings.app_url.startswith('https://') or not settings.api_url.startswith('https://'):
        raise RuntimeError('Production requires HTTPS URLs.')
    if not settings.database_url.startswith('postgresql'):
        raise RuntimeError('Production requires PostgreSQL.')
for name in ('jwt_secret', 'token_encryption_key'):
    if not getattr(settings, name):
        path = Path('.local') / name
        if not path.exists():
            path.write_text(secrets.token_urlsafe(48) if name == 'jwt_secret' else Fernet.generate_key().decode())
        setattr(settings, name, path.read_text().strip())
fernet = Fernet(settings.token_encryption_key.encode())
