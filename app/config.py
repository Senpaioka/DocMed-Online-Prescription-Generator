import os
from decouple import config

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

class Config:
    SECRET_KEY = config('WTF_CSRF_SECRET_KEY', default='default-secret-key')
    SQLALCHEMY_DATABASE_URI = config('DATABASE_URL', default='sqlite:///app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'uploads')
    SUPABASE_BUCKET = config('SUPABASE_BUCKET', default='')
    SUPABASE_BUCKET_NAME = config('SUPABASE_BUCKET_NAME', default='DocMed-Bucket')
    SUPABASE_BUCKET_API_KEY = config('SUPABASE_BUCKET_API_KEY', default='')
    SUPABASE_SECRET_ACCESS_KEY = config('SUPABASE_SECRET_ACCESS_KEY', default='')

    # Flask-Mailman configuration
    MAIL_SERVER = config('MAIL_SERVER', default='smtp.gmail.com')
    MAIL_PORT = config('MAIL_PORT', default=587, cast=int)
    MAIL_USE_TLS = config('MAIL_USE_TLS', default=True, cast=bool)
    MAIL_USE_SSL = config('MAIL_USE_SSL', default=False, cast=bool)
    MAIL_USERNAME = config('MAIL_USERNAME', default='')
    MAIL_PASSWORD = config('MAIL_PASSWORD', default='')
    MAIL_DEFAULT_SENDER = config('MAIL_DEFAULT_SENDER', default=config('MAIL_USERNAME', default='noreply@docmed.com'))

    # SSLCommerz Payment Gateway configuration
    SSLCOMMERZ_STORE_NAME = config('SSLCOMMERZ_STORE_NAME', default='testpersoy1iv')
    SSLCOMMERZ_STORE_ID = config('SSLCOMMERZ_STORE_ID')
    SSLCOMMERZ_STORE_PASSWORD = config('SSLCOMMERZ_STORE_PASSWORD')
    SSLCOMMERZ_IS_SANDBOX = config('SSLCOMMERZ_IS_SANDBOX', default=True, cast=bool)
    SSLCOMMERZ_API_URL = config('SSLCOMMERZ_API_URL', default='https://sandbox.sslcommerz.com/gwprocess/v4/api.php')
    SSLCOMMERZ_VALIDATION_URL = config('SSLCOMMERZ_VALIDATION_URL', default='https://sandbox.sslcommerz.com/validator/api/validationserverAPI.php')

    # Google Gemini AI configuration
    GEMINI_API_KEY = config('GEMINI_API_KEY', default='')
    GEMINI_API_KEYS = config('GEMINI_API_KEYS', default='')  # Optional comma-separated fallback keys
    GEMINI_MODEL = config('GEMINI_MODEL', default='gemini-3.5-flash')
    GEMINI_FALLBACK_MODELS = config('GEMINI_FALLBACK_MODELS', default='gemini-3.5-flash,gemini-3.1-flash-lite,gemini-3.5-flash-lite,gemini-3.6-flash,gemini-3.7-flash')


class DevelopmentConfig(Config):
    DEBUG = config('DEBUG', default=True, cast=bool)


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

