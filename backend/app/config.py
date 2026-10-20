from pathlib import Path
import os
import secrets
from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    app_env: str = 'development'
    demo_mode: bool = True
    ephemeral_demo: bool = False
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
    # Any OpenAI-compatible chat endpoint: Groq, OpenRouter, Google's compatibility endpoint, or a local Ollama.
    llm_base_url: str = ''
    llm_api_key: str = ''
    llm_model: str = ''
    llm_json_mode: bool = True
    # Shortcut: a free Groq key alone is enough (https://console.groq.com/keys).
    groq_api_key: str = ''
    bootstrap_email: str = ''
    bootstrap_password: str = ''
    # Hosted demos retain fictional data, but never use the published local login.
    private_demo: bool = False
    # Let visitors create their own account and private workspace. Throttled so a free database cannot be flooded.
    open_signup: bool = False
    resend_api_key: str = ''
    smtp_host: str = ''
    smtp_port: int = 587
    smtp_user: str = ''
    smtp_password: str = ''
    mail_from: str = ''
    signups_per_hour: int = 60
    max_organizations: int = 2000
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
if settings.groq_api_key and not settings.llm_api_key:
    settings.llm_api_key = settings.groq_api_key
    settings.llm_base_url = settings.llm_base_url or 'https://api.groq.com/openai/v1'
    settings.llm_model = settings.llm_model or 'llama-3.3-70b-versatile'
    if settings.ai_provider == 'openai' and not settings.openai_api_key:
        settings.ai_provider = 'compatible'
if settings.ai_provider not in ('openai', 'anthropic', 'compatible'):
    raise RuntimeError('AI_PROVIDER must be openai, anthropic or compatible.')
if not settings.demo_mode and (not settings.jwt_secret or not settings.token_encryption_key):
    raise RuntimeError('Live mode requires explicit JWT_SECRET and TOKEN_ENCRYPTION_KEY shared by all backend services.')
# Serverless hosts (Vercel) have a read-only filesystem and provide Postgres as POSTGRES_URL / DATABASE_URL.
# SQLAlchemy needs the psycopg 3 driver name; hosts hand out plain postgres:// URLs.
if settings.database_url.startswith('sqlite') and os.getenv('POSTGRES_URL'):
    settings.database_url = os.environ['POSTGRES_URL']
for _prefix in ('postgres://', 'postgresql://'):
    if settings.database_url.startswith(_prefix):
        settings.database_url = 'postgresql+psycopg://' + settings.database_url[len(_prefix):]
try:
    Path('.local').mkdir(exist_ok=True)
except OSError:
    pass
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
        try:
            if not path.exists():
                path.write_text(secrets.token_urlsafe(48) if name == 'jwt_secret' else Fernet.generate_key().decode())
            setattr(settings, name, path.read_text().strip())
        except OSError:
            # Read-only filesystem: use a per-process secret. Hosted deployments must set the env vars instead.
            setattr(settings, name, secrets.token_urlsafe(48) if name == 'jwt_secret' else Fernet.generate_key().decode())
fernet = Fernet(settings.token_encryption_key.encode())
