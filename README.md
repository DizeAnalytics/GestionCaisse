# Gestion des Caisses de Femmes - Togo

## Description du Projet

Application web Django pour la gestion des caisses de femmes au Togo, spécifiquement dans la région des Plateaux qui compte actuellement plus de 327 caisses. Cette plateforme centralise la gestion des membres, des prêts, des fonds et le suivi administratif.

## Fonctionnalités Principales

### 🏛️ Gestion Territoriale
- **Régions** : 5 régions du Togo
- **Préfectures** : Gestion par région
- **Communes** : Organisation par préfecture
- **Cantons** : Subdivision des communes
- **Villages** : Localisation précise des caisses

### 💰 Gestion des Caisses
- **Code unique automatique** : Format FKMCK[N][Nom_Association]
- **Localisation complète** : Village → Canton → Commune → Préfecture → Région
- **Membres dirigeants** : Présidente, Secrétaire, Trésorière
- **Limite de 30 femmes** par caisse
- **Statuts** : Active, Inactive, Suspendue

### 👥 Gestion des Membres
- **Identification unique** : Numéro de carte d'électeur
- **Informations personnelles** : Nom, prénoms, date de naissance, adresse, téléphone, photo
- **Rôles** : Présidente, Secrétaire, Trésorière, Membre simple
- **Statuts** : Actif, Inactif, Suspendu, Retraité

### 💳 Gestion des Prêts
- **Demande de prêt** : Montant, durée, motif
- **Validation** : Par administrateur uniquement
- **Statuts** : En attente, Validé, Rejeté, Bloqué, En cours, Remboursé, En retard
- **Suivi des remboursements** : Échéances, paiements, intérêts

### 🏦 Intégration Bancaire
- **Partenariat Ecobank** : Interface pour demandes de virement
- **Suivi des virements** : Statuts et références bancaires
- **Alimentation des caisses** : Virements automatiques

### 📊 Tableau de Bord
- **Statistiques globales** : Nombre de caisses, membres, prêts
- **Indicateurs financiers** : Montants en circulation, soldes disponibles
- **Répartition géographique** : Par région, préfecture, commune
- **Alertes** : Prêts en retard, fonds insuffisants, demandes en attente

## Architecture Technique

### Backend
- **Framework** : Django 5.2.5
- **API** : Django REST Framework (DRF)
- **Base de données** : PostgreSQL
- **Authentification** : Système Django standard + permissions personnalisées

### Sécurité
- **Contrôle d'accès** : Rôles et permissions par utilisateur
- **Audit trail** : Journalisation complète des actions
- **Validation des données** : Sérialiseurs DRF avec validation
- **Protection CSRF** : Activée sur tous les endpoints

### Modèles de Données
- **Relations hiérarchiques** : Région → Préfecture → Commune → Canton → Village
- **Entités métier** : Caisse, Membre, Prêt, Échéance, MouvementFond
- **Traçabilité** : AuditLog pour toutes les actions importantes

## Installation et Configuration

### Prérequis
- Python 3.13+
- PostgreSQL 12+
- pip

### Installation

1. **Cloner le projet**
```bash
git clone <repository-url>
cd projetcaisse
```

2. **Créer l'environnement virtuel**
```bash
python -m venv venv
```

3. **Activer l'environnement virtuel**
```bash
# Windows
.\venv\Scripts\Activate.ps1

# Linux/Mac
source venv/bin/activate
```

4. **Installer les dépendances**
```bash
pip install -r requirements.txt
```

5. **Configurer la base de données**
```bash
# Créer la base PostgreSQL
createdb caisses_femmes

# Configurer les variables d'environnement
cp config.env .env
# Éditer .env avec vos paramètres de base de données
```

6. **Appliquer les migrations**
```bash
python manage.py makemigrations
python manage.py migrate
```

7. **Initialiser les données de base**
```bash
python manage.py init_data
```

8. **Créer un super utilisateur**
```bash
python manage.py createsuperuser
```

9. **Lancer le serveur**
```bash
python manage.py runserver
```

### Accès
- **Interface d'administration** : http://localhost:8000/admin/
- **API REST** : http://localhost:8000/gestion-caisses/api/
- **Identifiants par défaut** : admin/admin123

## Structure de l'API

### Endpoints Principaux

#### Territorial
- `GET /api/regions/` - Liste des régions
- `GET /api/prefectures/` - Liste des préfectures
- `GET /api/communes/` - Liste des communes
- `GET /api/cantons/` - Liste des cantons
- `GET /api/villages/` - Liste des villages

#### Gestion des Caisses
- `GET /api/caisses/` - Liste des caisses
- `POST /api/caisses/` - Créer une caisse
- `GET /api/caisses/{id}/` - Détails d'une caisse
- `PUT /api/caisses/{id}/` - Modifier une caisse
- `GET /api/caisses/{id}/stats/` - Statistiques d'une caisse

#### Gestion des Membres
- `GET /api/membres/` - Liste des membres
- `POST /api/membres/` - Créer un membre
- `GET /api/membres/{id}/` - Détails d'un membre
- `GET /api/membres/par-caisse/` - Membres groupés par caisse

#### Gestion des Prêts
- `GET /api/prets/` - Liste des prêts
- `POST /api/prets/` - Créer un prêt
- `POST /api/prets/{id}/valider/` - Valider un prêt
- `POST /api/prets/{id}/rejeter/` - Rejeter un prêt
- `GET /api/prets/en-retard/` - Prêts en retard

#### Tableau de Bord
- `GET /api/dashboard/stats/` - Statistiques globales
- `GET /api/dashboard/alertes/` - Alertes du système

### Authentification
L'API utilise l'authentification par session Django. Tous les endpoints nécessitent une authentification sauf indication contraire.

## Utilisation

### 1. Création d'une Caisse
1. Se connecter à l'interface d'administration
2. Aller dans "Caisses" → "Ajouter une caisse"
3. Remplir les informations : nom de l'association, localisation
4. Le code unique sera généré automatiquement

### 2. Ajout de Membres
1. Dans la caisse créée, ajouter des membres
2. Chaque membre doit avoir un numéro de carte d'électeur unique
3. Maximum 30 membres actifs par caisse

### 3. Gestion des Prêts
1. Un membre peut demander un prêt
2. L'administrateur valide ou rejette la demande
3. Si validé, le prêt passe en statut "En cours"
4. Suivi des remboursements via les échéances

### 4. Mouvements de Fonds
1. Alimentation de la caisse par virement bancaire
2. Décaissement lors de l'octroi d'un prêt
3. Remboursements automatiques
4. Historique complet des mouvements

## Développement

### Structure du Projet
```
projetcaisse/
├── caisses_femmes/          # Configuration du projet
├── gestion_caisses/         # Application principale
│   ├── models.py           # Modèles de données
│   ├── views.py            # Vues API
│   ├── serializers.py      # Sérialiseurs DRF
│   ├── admin.py            # Interface d'administration
│   └── urls.py             # URLs de l'application
├── templates/               # Templates HTML
├── static/                  # Fichiers statiques
├── media/                   # Fichiers uploadés
├── logs/                    # Fichiers de logs
├── manage.py                # Script de gestion Django
└── requirements.txt         # Dépendances Python
```

### Ajout de Nouvelles Fonctionnalités
1. **Modèle** : Créer dans `models.py`
2. **Sérialiseur** : Ajouter dans `serializers.py`
3. **Vue** : Implémenter dans `views.py`
4. **Admin** : Configurer dans `admin.py`
5. **URLs** : Ajouter dans `urls.py`
6. **Migration** : `python manage.py makemigrations`

## Tests

### Tests Unitaires
```bash
python manage.py test gestion_caisses
```

### Tests de l'API
```bash
# Utiliser un outil comme Postman ou curl
curl -X GET http://localhost:8000/gestion-caisses/api/caisses/ \
     -H "Authorization: Session <session_id>"
```

## Déploiement

### Production
1. **Variables d'environnement** : Configurer `DEBUG=False`
2. **Base de données** : PostgreSQL avec authentification sécurisée
3. **Serveur web** : Nginx + Gunicorn
4. **Fichiers statiques** : Collecter avec `python manage.py collectstatic`
5. **Sécurité** : HTTPS, HSTS, CSP

### Docker (optionnel)
```bash
# Construire l'image
docker build -t caisses-femmes .

# Lancer le conteneur
docker run -p 8000:8000 caisses-femmes
```

## Support et Maintenance

### Logs
- **Application** : `logs/django.log`
- **Serveur** : Logs du serveur web
- **Base de données** : Logs PostgreSQL

### Sauvegarde
- **Base de données** : Sauvegarde PostgreSQL quotidienne
- **Fichiers média** : Sauvegarde des photos et documents
- **Configuration** : Versioning des fichiers de configuration

### Monitoring
- **Santé de l'application** : Endpoint `/health/`
- **Performance** : Métriques Django
- **Erreurs** : Logs d'erreur et notifications

## Contribution

### Standards de Code
- **Python** : PEP 8
- **Django** : Style guide officiel
- **Documentation** : Docstrings en français
- **Tests** : Couverture minimale de 80%

### Workflow Git
1. Fork du projet
2. Branche feature : `feature/nom-fonctionnalite`
3. Tests et validation
4. Pull Request avec description détaillée

## Licence

Ce projet est développé pour la gestion des caisses de femmes au Togo. Tous droits réservés.

## Contact

Pour toute question ou support :
- **Email** : support@caisses-femmes.tg
- **Documentation** : Consulter l'interface d'administration
- **Issues** : Utiliser le système de tickets du projet

---

**Version** : 1.0.0  
**Dernière mise à jour** : Décembre 2024  
**Développé avec** : Django 5.2.5, Python 3.13
