# Gestion des Caisses

Ce dépôt contient l'application Django de gestion des caisses.

- Guide utilisateur: [docs/Guide_Utilisateur.md](docs/Guide_Utilisateur.md)

## Démarrage rapide
Voir le guide utilisateur.

## Environnement Python

- Version recommandée: Python 3.13
- Le fichier `.python-version` est fourni pour les environnements gérés par pyenv.

### Installation locale (Python 3.13)

1) Créez et activez un environnement virtuel:

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

2) Installez les dépendances:

```bash
pip install -r requirements.txt
```

3) Lancez les migrations et démarrez le serveur:

```bash
python manage.py migrate
python manage.py runserver
```

### Déploiement sur PythonAnywhere (Python 3.13)

1) Créez un virtualenv 3.13 dans une console Bash:

```bash
mkvirtualenv --python=/usr/bin/python3.13 gestioncaisse-venv
workon gestioncaisse-venv
pip install -r /home/USERNAME/GestionCaisse/requirements.txt
```

2) Configurez l'application dans l'onglet Web:

- Choisissez Python 3.13
- Associez le virtualenv `gestioncaisse-venv`
- Fichier WSGI: utilisez `caisses_femmes/wsgi.py`
- Variable d'environnement: `DJANGO_SETTINGS_MODULE=caisses_femmes.settings`

3) Initialisez la base et les statiques:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

4) Rechargez l'application depuis l'onglet Web.