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
