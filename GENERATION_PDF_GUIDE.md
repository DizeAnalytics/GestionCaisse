# Guide de Génération des PDFs - Système de Gestion des Caisses

## 🆕 Nouvelles Fonctionnalités (Mise à jour)

### 📸 Photos des Membres
- **PDF Individuel** : Les PDFs des membres individuels affichent maintenant la photo du membre dans un cadre dédié
- **Gestion des Photos** : Les photos sont stockées dans le dossier `media/photos_membres/`
- **Fallback** : Si aucune photo n'est disponible, un message "📷 Aucune photo" s'affiche

### ✍️ Signatures Numériques
Tous les PDFs générés par le système incluent maintenant les signatures numériques suivantes :

#### 1. Président Général de toutes les caisses
- **Modèle** : `PresidentGeneral` (nouveau)
- **Gestion** : Interface d'administration dédiée
- **Contrainte** : Un seul président général actif à la fois
- **Stockage** : `media/signatures_president_general/`

#### 2. Responsables de la Caisse
- **Présidente** : Signature de la présidente de la caisse
- **Trésorière** : Signature de la trésorière de la caisse  
- **Secrétaire** : Signature de la secrétaire de la caisse
- **Stockage** : `media/signatures_membres/`

### 🔧 Configuration des Signatures

#### Ajouter un Président Général
1. Aller dans l'administration Django
2. Section "Présidents Généraux"
3. Cliquer sur "Ajouter un Président Général"
4. Remplir les informations :
   - Nom et prénoms
   - Numéro de carte d'électeur
   - Date de naissance
   - Adresse et téléphone
   - **Photo** (optionnel)
   - **Signature** (recommandé)
5. Statut : "Actif" (désactive automatiquement les autres)

#### Ajouter des Signatures aux Membres
1. Aller dans l'administration Django
2. Section "Membres"
3. Modifier un membre (présidente, trésorière, secrétaire)
4. Ajouter une signature dans le champ "Signature"
5. Sauvegarder

## 📋 Fonctionnalités Existantes

### Génération de PDFs depuis le Frontend

#### 1. PDF de la Liste des Membres
- **Bouton** : Disponible dans la section "Membres" du dashboard
- **Fonction JavaScript** : `generateMembresListePDF(caisseId)`
- **Endpoint API** : `/gestion-caisses/api/caisses/{id}/membres_liste_pdf/`
- **Contenu** :
  - Informations de la caisse
  - Liste complète des membres avec leurs détails
  - Statistiques des membres
  - **Signatures** : Président Général + Responsables de la caisse

#### 2. PDF Individuel d'un Membre
- **Bouton** : Disponible sur chaque carte de membre
- **Fonction JavaScript** : `generateMembrePDF(membreId)`
- **Endpoint API** : `/gestion-caisses/api/membres/{id}/fiche_pdf/`
- **Contenu** :
  - **Photo du membre** dans un cadre dédié
  - Informations personnelles complètes
  - Informations de la caisse
  - Historique des prêts (si applicable)
  - **Signatures** : Président Général + Responsables de la caisse

### Utilisation depuis le Frontend

#### Boutons de Génération
```html
<!-- Liste des membres -->
<button onclick="generateMembresListePDF({{ caisse.id }})" class="btn btn-primary">
    📄 Générer PDF Liste Membres
</button>

<!-- Fiche membre individuelle -->
<button onclick="generateMembrePDF({{ membre.id }})" class="btn btn-info">
    📄 Générer PDF Membre
</button>
```

#### Fonctions JavaScript
```javascript
// Génération PDF liste des membres
async function generateMembresListePDF(caisseId) {
    try {
        const button = event.target;
        const originalText = button.innerHTML;
        button.disabled = true;
        button.innerHTML = '⏳ Génération...';
        
        const response = await fetch(`/gestion-caisses/api/caisses/${caisseId}/membres_liste_pdf/`, {
            method: 'GET',
            headers: { 'X-CSRFToken': getCSRFToken() }
        });
        
        if (!response.ok) throw new Error('Erreur lors de la génération du PDF');
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = `liste_membres_caisse_${caisseId}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        showToast('PDF de la liste des membres généré avec succès !', 'success');
    } catch (error) {
        console.error('Erreur lors de la génération du PDF:', error);
        showToast('Erreur lors de la génération du PDF', 'error');
    } finally {
        const button = event.target;
        button.disabled = false;
        button.innerHTML = originalText;
    }
}

// Génération PDF membre individuel
async function generateMembrePDF(membreId) {
    try {
        const button = event.target;
        const originalText = button.innerHTML;
        button.disabled = true;
        button.innerHTML = '⏳ Génération...';
        
        const response = await fetch(`/gestion-caisses/api/membres/${membreId}/fiche_pdf/`, {
            method: 'GET',
            headers: { 'X-CSRFToken': getCSRFToken() }
        });
        
        if (!response.ok) throw new Error('Erreur lors de la génération du PDF');
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = `fiche_membre_${membreId}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        showToast('PDF de la fiche membre généré avec succès !', 'success');
    } catch (error) {
        console.error('Erreur lors de la génération du PDF:', error);
        showToast('Erreur lors de la génération du PDF', 'error');
    } finally {
        const button = event.target;
        button.disabled = false;
        button.innerHTML = originalText;
    }
}
```

### Utilisation via l'API

#### Endpoints Disponibles

##### 1. Liste des Membres d'une Caisse
```http
GET /gestion-caisses/api/caisses/{caisse_id}/membres_liste_pdf/
```

**Paramètres :**
- `caisse_id` : ID de la caisse

**Réponse :**
- Type : `application/pdf`
- Contenu : PDF avec la liste des membres
- Nom de fichier : `liste_membres_{code_caisse}_{date}.pdf`

##### 2. Fiche Individuelle d'un Membre
```http
GET /gestion-caisses/api/membres/{membre_id}/fiche_pdf/
```

**Paramètres :**
- `membre_id` : ID du membre

**Réponse :**
- Type : `application/pdf`
- Contenu : PDF avec les informations du membre
- Nom de fichier : `fiche_membre_{nom_membre}_{date}.pdf`

#### Exemple d'Utilisation avec cURL
```bash
# Générer PDF liste des membres
curl -X GET "http://localhost:8000/gestion-caisses/api/caisses/1/membres_liste_pdf/" \
     -H "X-CSRFToken: votre_token_csrf" \
     -o liste_membres.pdf

# Générer PDF membre individuel
curl -X GET "http://localhost:8000/gestion-caisses/api/membres/1/fiche_pdf/" \
     -H "X-CSRFToken: votre_token_csrf" \
     -o fiche_membre.pdf
```

## 🛠️ Détails Techniques

### Backend (Django)

#### Fonctions de Génération
- `generate_membres_liste_pdf(caisse)` : Génère le PDF de la liste des membres
- `generate_membre_individual_pdf(membre)` : Génère le PDF individuel d'un membre

#### Modèles Utilisés
- `Caisse` : Informations de la caisse
- `Membre` : Informations des membres (avec photos et signatures)
- `PresidentGeneral` : Informations du président général (nouveau)

#### Technologies
- **ReportLab** : Génération des PDFs
- **Pillow** : Traitement des images (photos et signatures)
- **Django REST Framework** : API endpoints

### Frontend (JavaScript)

#### Fonctions Requises
- `getCSRFToken()` : Récupération du token CSRF
- `showToast(message, type)` : Affichage des notifications
- `USER_CAISE_ID` : ID de la caisse de l'utilisateur connecté

#### Gestion des Erreurs
- Affichage d'indicateurs de chargement
- Gestion des erreurs réseau
- Messages de succès/erreur via toast
- Restauration de l'état des boutons

## 🔍 Dépannage

### Problèmes Courants

#### 1. Photos non affichées
**Symptômes :** "📷 Photo non disponible" s'affiche
**Solutions :**
- Vérifier que la photo est bien uploadée
- Vérifier les permissions du dossier `media/photos_membres/`
- Vérifier le format de l'image (JPG, PNG recommandés)

#### 2. Signatures non affichées
**Symptômes :** "Signature non disponible" s'affiche
**Solutions :**
- Vérifier qu'un Président Général actif est configuré
- Vérifier que les responsables de la caisse ont des signatures
- Vérifier les permissions du dossier `media/signatures_*/`

#### 3. Erreur 400 lors de la génération
**Symptômes :** "Échec de la connexion: 400"
**Solutions :**
- Vérifier que le serveur Django est démarré
- Vérifier que l'utilisateur est connecté
- Vérifier le token CSRF

#### 4. Erreur 403 (Forbidden)
**Symptômes :** "Échec de la connexion: 403"
**Solutions :**
- Vérifier les permissions de l'utilisateur
- Vérifier que l'utilisateur a accès à la caisse/membre

### Logs et Debugging

#### Logs Django
```python
# Dans settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'logs/pdf_generation.log',
        },
    },
    'loggers': {
        'gestion_caisses.utils': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
```

#### Debug Frontend
```javascript
// Activer les logs détaillés
console.log('CSRF Token:', getCSRFToken());
console.log('User Caisse ID:', USER_CAISE_ID);
console.log('Response status:', response.status);
```

## 📁 Structure des Fichiers

```
media/
├── photos_membres/          # Photos des membres
├── signatures_membres/      # Signatures des membres
└── signatures_president_general/  # Signatures du président général

gestion_caisses/
├── models.py               # Modèles (Membre, PresidentGeneral)
├── utils.py               # Fonctions de génération PDF
├── views.py               # ViewSets et endpoints API
├── admin.py               # Configuration admin
└── templates/
    └── gestion_caisses/
        └── dashboard.html  # Interface frontend
```

## 🔄 Mise à Jour

### Nouvelles Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### Nouveaux Modèles
- `PresidentGeneral` : Gestion du président général
- Champ `signature` ajouté au modèle `Membre`

### Nouvelles Fonctionnalités
- Affichage des photos dans les PDFs individuels
- Signatures numériques sur tous les PDFs
- Interface d'administration pour le président général

---

**Note :** Ce guide est mis à jour régulièrement avec les nouvelles fonctionnalités. Pour toute question ou problème, consultez les logs ou contactez l'équipe de développement.
