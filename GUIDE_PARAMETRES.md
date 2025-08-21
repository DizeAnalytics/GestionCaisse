# Guide des Paramètres de l'Application

Ce guide explique comment configurer et utiliser le modèle `Parametre` pour personnaliser l'application de gestion des caisses.

## Vue d'ensemble

Le modèle `Parametre` centralise toutes les informations administratives et personnelles de l'application, permettant une personnalisation complète sans modification du code.

## Configuration via Django Admin

### Accès aux paramètres
1. Connectez-vous à l'interface d'administration Django
2. Naviguez vers la section "Paramètres"
3. Vous pouvez créer ou modifier un seul ensemble de paramètres actifs

### Structure des paramètres
Les paramètres sont organisés en sections logiques :

#### Informations de base
- **Nom de l'application** : Nom affiché sur toutes les pages et PDFs
- **Logo** : Image du logo de l'application
- **Description** : Description de l'application
- **Version** : Version actuelle du logiciel

#### Contact
- **Téléphone principal/secondaire** : Numéros de contact
- **Email de contact** : Adresse email
- **Site web** : URL du site officiel

#### Adresse et siège social
- **Siège social** : Adresse complète
- **Adresse postale** : Adresse pour correspondance
- **Boîte postale** : BP si applicable
- **Ville** et **Pays** : Localisation

#### Président Général/PDG
- **Nom du Président Général** : Nom complet
- **Titre** : Titre officiel (par défaut "Président Général")
- **Signature** : Image de la signature pour les PDFs

#### Personnel
- **Directeur Technique** : Nom du DT
- **Directeur Financier** : Nom du DF
- **Directeur Administratif** : Nom du DA

#### Informations légales
- **Numéro d'agrément** : Numéro officiel
- **Date d'agrément** : Date d'obtention
- **Autorité d'agrément** : Organisme d'agrément
- **Copyright** : Texte de copyright
- **Mentions légales** : Mentions légales complètes

#### Paramètres système
- **Devise** : Devise utilisée (par défaut "FCFA")
- **Langue par défaut** : Langue de l'interface
- **Fuseau horaire** : Fuseau horaire local

## Intégration dans l'Application

### Page de Connexion
Le logo et le nom de l'application sont automatiquement affichés sur la page de connexion :

- **Logo** : Si un logo est configuré, il remplace l'icône par défaut (€)
- **Nom de l'application** : Remplace "CashFlow Pro FKM" par le nom configuré
- **Description** : Affiche la description de l'application sous le nom

### Génération de PDFs
Les paramètres sont utilisés dans tous les PDFs générés :

```python
from gestion_caisses.utils import get_parametres_application

parametres = get_parametres_application()
nom_app = parametres['nom_application']
logo = parametres['logo']
president = parametres['nom_president_general']
```

### Utilisation dans les vues
Les vues de connexion récupèrent automatiquement les paramètres :

```python
def login_view(request):
    parametres = get_parametres_application()
    context = {
        'nom_application': parametres['nom_application'],
        'logo': parametres['logo'],
        'description_application': parametres['description_application'],
    }
    return render(request, 'gestion_caisses/login.html', context)
```

## Gestion des Fichiers

### Logo de l'application
- **Format recommandé** : PNG ou JPG
- **Taille recommandée** : 200x200 pixels minimum
- **Stockage** : Dossier `media/logos/`
- **Affichage** : Redimensionné automatiquement sur la page de connexion

### Signature du Président Général
- **Format recommandé** : PNG avec fond transparent
- **Taille recommandée** : 300x150 pixels
- **Stockage** : Dossier `media/signatures_pdg/`
- **Utilisation** : Intégrée dans tous les PDFs officiels

## Sécurité et Contrôle d'Accès

### Permissions d'administration
- Seuls les super-utilisateurs peuvent créer de nouveaux paramètres
- Un seul ensemble de paramètres peut être actif à la fois
- Les paramètres actifs ne peuvent pas être supprimés

### Validation des données
- Le modèle inclut une méthode `clean()` pour valider les données
- Vérification automatique qu'un seul ensemble est actif
- Validation des formats de fichiers et tailles

## Fonctions Utilitaires

### Récupération des paramètres
```python
from gestion_caisses.utils import get_parametres_application

# Récupérer tous les paramètres actifs
parametres = get_parametres_application()

# Utiliser un paramètre spécifique
nom_app = parametres['nom_application']
logo = parametres['logo']
```

### Valeurs par défaut
Si aucun paramètre n'est configuré, des valeurs par défaut sont utilisées :
- Nom de l'application : "CAISSE DE SOLIDARITÉ"
- Logo : Aucun (icône par défaut)
- Président Général : Aucun nom configuré

## Maintenance et Mise à Jour

### Sauvegarde des paramètres
- Sauvegardez régulièrement les paramètres via l'admin Django
- Exportez les données si nécessaire pour migration

### Mise à jour des paramètres
1. Accédez à l'admin Django
2. Modifiez les paramètres existants
3. Sauvegardez pour appliquer les changements
4. Les modifications sont immédiatement visibles

### Gestion des fichiers
- Les anciens fichiers (logo, signature) ne sont pas automatiquement supprimés
- Nettoyez manuellement les fichiers inutilisés
- Vérifiez les permissions des dossiers media

## Dépannage

### Problèmes courants

#### Logo non affiché
- Vérifiez que le fichier existe dans `media/logos/`
- Vérifiez les permissions du fichier
- Vérifiez que le chemin est correct dans l'admin

#### Nom de l'application non mis à jour
- Videz le cache du navigateur
- Vérifiez que les paramètres sont actifs
- Redémarrez le serveur Django si nécessaire

#### Erreur de validation
- Vérifiez qu'un seul ensemble de paramètres est actif
- Vérifiez les formats de fichiers
- Consultez les logs Django pour plus de détails

### Logs et débogage
```python
import logging
logger = logging.getLogger(__name__)

# Dans vos vues ou utilitaires
try:
    parametres = get_parametres_application()
except Exception as e:
    logger.error(f"Erreur lors de la récupération des paramètres: {e}")
```

## Exemples d'Utilisation

### Template Django
```html
{% if logo %}
    <img src="{{ logo.url }}" alt="Logo" class="logo-image">
{% else %}
    <div class="logo-icon">€</div>
{% endif %}

<h1>{{ nom_application|default:"Application" }}</h1>
<p>{{ description_application|default:"Description par défaut" }}</p>
```

### Vue Django
```python
def ma_vue(request):
    parametres = get_parametres_application()
    context = {
        'app_name': parametres['nom_application'],
        'contact_phone': parametres['telephone_principal'],
        'president_name': parametres['nom_president_general'],
    }
    return render(request, 'mon_template.html', context)
```

### Génération de PDF
```python
def generer_pdf(request):
    parametres = get_parametres_application()
    
    # Utiliser le nom de l'application
    titre = f"{parametres['nom_application']} - Rapport"
    
    # Utiliser la signature du président
    if parametres['signature_president_general']:
        signature = Image(parametres['signature_president_general'].path)
    
    # Générer le PDF avec les paramètres
    # ...
```

Ce guide couvre tous les aspects de la configuration et de l'utilisation du modèle `Parametre` pour personnaliser l'application selon vos besoins spécifiques.
