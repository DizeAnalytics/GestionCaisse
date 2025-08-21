# Guide des Rapports de Caisse

## Vue d'ensemble

Le système de rapports de caisse permet de générer des analyses détaillées et des statistiques complètes sur l'activité d'une caisse. Ces rapports sont accessibles depuis la section "Rapports" du dashboard frontend.

## Types de Rapports Disponibles

### 1. Rapport Général
**Description :** Vue d'ensemble complète de la caisse
**Contenu :**
- Informations de base de la caisse (nom, code, date de création, statut)
- Statistiques des membres (total, actifs, inactifs, suspendus, par sexe)
- Statistiques des prêts (total, en cours, remboursés, en retard, montant moyen)
- État des fonds (fond initial, disponible, total prêts, solde disponible)
- Échéances en retard

### 2. Rapport Financier
**Description :** Analyse détaillée des mouvements financiers
**Contenu :**
- Fonds actuels de la caisse
- Statistiques des mouvements de fonds par type
- Évolution chronologique des fonds
- Détails de chaque mouvement avec solde après opération

### 3. Rapport des Prêts
**Description :** Analyse complète de l'activité de prêts
**Contenu :**
- Statistiques par statut de prêt
- Statistiques par membre
- Prêts en retard (nombre et montant)
- Détails complets de tous les prêts

### 4. Rapport des Membres
**Description :** Analyse détaillée de la composition des membres
**Contenu :**
- Statistiques par statut de membre
- Statistiques par sexe
- Statistiques par rôle (Présidente, Secrétaire, Trésorière, Membre)
- Détails complets de tous les membres avec leur historique de prêts

### 5. Rapport des Échéances
**Description :** Suivi détaillé des échéances de remboursement
**Contenu :**
- Statistiques générales des échéances
- Échéances en retard (nombre et montant)
- Échéances à venir (prochaines 30 jours)
- Détails de toutes les échéances

## Utilisation du Système de Rapports

### Accès aux Rapports
1. Connectez-vous au dashboard frontend
2. Cliquez sur l'onglet "📈 Rapports" dans la barre de navigation
3. Sélectionnez le type de rapport souhaité
4. Optionnellement, définissez une période de filtrage
5. Cliquez sur "Charger" pour afficher le rapport

### Filtres Disponibles
- **Date de début :** Limite l'analyse aux données à partir de cette date
- **Date de fin :** Limite l'analyse aux données jusqu'à cette date
- **Type de rapport :** Sélection du type d'analyse à effectuer

### Génération de PDF
Chaque type de rapport peut être exporté en PDF :
1. Cliquez sur le bouton PDF correspondant au type de rapport
2. Le PDF sera automatiquement téléchargé
3. Le fichier sera nommé selon le format : `rapport_[type]_[date].pdf`

## API Endpoints

### Endpoint Principal
```
GET /gestion-caisses/api/rapports-caisse/
```

### Paramètres
- `type` (requis) : Type de rapport ('general', 'financier', 'prets', 'membres', 'echeances')
- `date_debut` (optionnel) : Date de début au format YYYY-MM-DD
- `date_fin` (optionnel) : Date de fin au format YYYY-MM-DD
- `format` (optionnel) : 'pdf' pour générer un PDF

### Exemples d'utilisation

#### Rapport général pour toute la période
```
GET /gestion-caisses/api/rapports-caisse/?type=general
```

#### Rapport financier pour une période spécifique
```
GET /gestion-caisses/api/rapports-caisse/?type=financier&date_debut=2024-01-01&date_fin=2024-12-31
```

#### Export PDF d'un rapport de prêts
```
GET /gestion-caisses/api/rapports-caisse/?type=prets&format=pdf
```

## Structure des Données Retournées

### Rapport Général
```json
{
  "caisse": {
    "nom": "Nom de la caisse",
    "code": "FKMCK1NomCaisse",
    "date_creation": "01/01/2024",
    "statut": "ACTIVE"
  },
  "membres": {
    "total": 25,
    "actifs": 20,
    "inactifs": 3,
    "suspendus": 2,
    "femmes": 18,
    "hommes": 7
  },
  "prets": {
    "total": 15,
    "en_cours": 8,
    "rembourses": 5,
    "en_retard": 2,
    "montant_total": 5000000.00,
    "montant_rembourse": 3000000.00,
    "montant_moyen": 333333.33
  },
  "fonds": {
    "fond_initial": 10000000.00,
    "fond_disponible": 8000000.00,
    "montant_total_prets": 5000000.00,
    "solde_disponible": 3000000.00
  },
  "periode": {
    "debut": "01/01/2024",
    "fin": "31/12/2024"
  }
}
```

### Rapport Financier
```json
{
  "caisse": {
    "nom": "Nom de la caisse",
    "code": "FKMCK1NomCaisse"
  },
  "fonds_actuels": {
    "fond_initial": 10000000.00,
    "fond_disponible": 8000000.00,
    "montant_total_prets": 5000000.00,
    "solde_disponible": 3000000.00
  },
  "mouvements": {
    "stats_par_type": [
      {
        "type_mouvement": "ALIMENTATION",
        "nombre": 5,
        "total": 2000000.00
      }
    ],
    "evolution": [
      {
        "date": "01/01/2024",
        "type": "ALIMENTATION",
        "montant": 1000000.00,
        "solde": 11000000.00,
        "description": "Alimentation initiale"
      }
    ],
    "total_mouvements": 15
  },
  "periode": {
    "debut": "01/01/2024",
    "fin": "31/12/2024"
  }
}
```

## Fonctionnalités Avancées

### Filtrage Temporel
- Les rapports peuvent être filtrés par période pour analyser des données spécifiques
- Si aucune période n'est spécifiée, toutes les données sont incluses
- Les dates sont au format français (DD/MM/YYYY) dans l'affichage

### Statistiques en Temps Réel
- Toutes les statistiques sont calculées en temps réel
- Les données reflètent l'état actuel de la base de données
- Les calculs incluent les relations entre les différents modèles

### Interface Responsive
- L'interface s'adapte aux différentes tailles d'écran
- Les tableaux sont scrollables horizontalement sur mobile
- Les cartes de statistiques se réorganisent automatiquement

### Codes Couleur
- Les badges utilisent un système de couleurs cohérent :
  - **Vert** : Statuts positifs (Actif, Payé, Remboursé)
  - **Rouge** : Statuts négatifs (En retard, Rejeté)
  - **Orange** : Statuts d'attention (En attente, À payer)
  - **Bleu** : Statuts neutres (En cours, Validé)

## Sécurité et Permissions

### Contrôle d'Accès
- Seuls les utilisateurs connectés peuvent accéder aux rapports
- Chaque utilisateur ne peut voir que les rapports de sa caisse
- Les administrateurs peuvent voir les rapports de toutes les caisses

### Validation des Données
- Toutes les dates sont validées avant traitement
- Les paramètres sont nettoyés pour éviter les injections
- Les erreurs sont gérées gracieusement avec des messages informatifs

## Maintenance et Performance

### Optimisation des Requêtes
- Les requêtes utilisent des `select_related` et `prefetch_related` pour optimiser les performances
- Les agrégations sont effectuées au niveau de la base de données
- Les résultats sont mis en cache temporairement

### Gestion des Erreurs
- Les erreurs de base de données sont capturées et loggées
- Des messages d'erreur informatifs sont affichés à l'utilisateur
- Les timeouts sont gérés pour les requêtes longues

## Évolutions Futures

### Fonctionnalités Prévues
- Graphiques interactifs pour visualiser les tendances
- Export Excel en plus du PDF
- Rapports comparatifs entre caisses
- Alertes automatiques basées sur les rapports
- Planification de rapports récurrents

### Améliorations Techniques
- Mise en cache des rapports fréquemment consultés
- Génération asynchrone des PDF volumineux
- API pour intégration avec d'autres systèmes
- Notifications par email des rapports générés

## Support et Dépannage

### Problèmes Courants
1. **Rapport vide** : Vérifiez que la caisse a des données
2. **Erreur de chargement** : Vérifiez la connexion réseau
3. **PDF non généré** : Vérifiez les permissions d'écriture

### Logs et Debugging
- Les erreurs sont loggées dans les logs Django
- Utilisez la console du navigateur pour déboguer les problèmes JavaScript
- Vérifiez les requêtes réseau dans les outils de développement

---

*Ce guide est mis à jour régulièrement pour refléter les nouvelles fonctionnalités et améliorations du système de rapports.*
