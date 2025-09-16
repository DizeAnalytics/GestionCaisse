"""
Configuration Django pour SQLite (développement/test)
"""
from .settings import *

# Base de données SQLite pour les tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Configuration des fichiers statiques pour SQLite
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# En mode développement, servir les fichiers statiques directement
if DEBUG:
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# Configuration de développement pour éviter les erreurs 400
DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '*']

# Désactiver temporairement les vérifications CSRF pour le développement
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

# Configuration CORS pour le développement
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# Configuration CSRF pour le développement
CSRF_TRUSTED_ORIGINS = ['http://localhost:8000', 'http://127.0.0.1:8000']
CSRF_COOKIE_DOMAIN = None
CSRF_USE_SESSIONS = False

# Configuration des sessions
SESSION_COOKIE_HTTPONLY = False
SESSION_COOKIE_SAMESITE = 'Lax'
