# 💸 Système de Gestion des Dépenses - Gestion des Caisses

## 📋 Vue d'ensemble

Le système de gestion des dépenses permet aux utilisateurs de gérer les dépenses de chaque caisse. Le solde des dépenses provient des frais de solidarité et des frais de pénalités collectés par la caisse.

**Formule :** `Solde Dépense = Montant total solidarité + Montant total pénalité - Dépenses approuvées`

## 🏗️ Architecture

### Modèle de données

- **Depense** : Modèle principal pour les dépenses
- **Caisse** : Relation avec la caisse concernée
- **Membre** : Responsable de la dépense
- **Catégories** : SOLIDARITE, PENALITE, AUTRE
- **Statuts** : EN_COURS, APPROUVEE, REJETEE, TERMINEE

### Fonctionnalités

1. **Création de dépenses** avec justification obligatoire
2. **Approbation/Rejet** des dépenses en attente
3. **Suivi des statuts** et historique des modifications
4. **Calcul automatique** du solde disponible
5. **Validation** des montants selon le solde disponible

## 🚀 Utilisation

### 1. Accès à l'onglet Dépenses

- Connectez-vous au dashboard
- Cliquez sur l'onglet "💸 Dépenses" dans la navigation

### 2. Créer une nouvelle dépense

1. Cliquez sur "Nouvelle Dépense"
2. Remplissez le formulaire :
   - **Caisse** : Sélectionnez la caisse concernée
   - **Catégorie** : Choisissez le type de dépense
   - **Montant** : Entrez le montant en FCFA
   - **Date** : Date de la dépense
   - **Responsable** : Membre responsable
   - **Description** : Détails de la dépense
   - **Justificatif** : Justification obligatoire
3. Cliquez sur "Enregistrer"

### 3. Gérer les dépenses

- **Voir** : Consulter les détails d'une dépense
- **Modifier** : Éditer une dépense existante
- **Approuver** : Approuver une dépense en attente
- **Rejeter** : Rejeter une dépense avec motif

### 4. Rapports et statistiques

- **Statistiques en temps réel** : Solde disponible, dépenses approuvées, en attente, rejetées
- **Filtres** : Par caisse, catégorie, statut
- **Export PDF** : Rapport complet des dépenses

## 📊 Catégories de dépenses

### 1. **Frais de solidarité** (SOLIDARITE)
- Aide médicale pour membres
- Soutien financier aux familles en difficulté
- Achat de médicaments
- Transport pour consultations
- Aide alimentaire d'urgence

### 2. **Frais de pénalités** (PENALITE)
- Pénalités de retard de remboursement
- Amendes pour absences aux réunions
- Sanctions pour non-respect des règles
- Pénalités de retard de cotisation

### 3. **Autres dépenses** (AUTRE)
- Matériel de bureau
- Frais de transport pour réunions
- Fournitures diverses
- Frais de communication
- Maintenance d'équipements

## 🔐 Sécurité et validation

### Règles métier

1. **Justification obligatoire** : Toute dépense doit être justifiée
2. **Solde suffisant** : Une dépense ne peut être approuvée que si le solde est suffisant
3. **Responsabilité** : Le responsable doit appartenir à la caisse
4. **Traçabilité** : Toutes les actions sont tracées avec l'utilisateur

### Contrôles automatiques

- Validation des montants positifs
- Vérification de l'appartenance du responsable à la caisse
- Calcul automatique du solde disponible
- Mise à jour automatique des dates d'approbation

## 📱 Interface utilisateur

### Dashboard des dépenses

- **Cartes de statistiques** : Solde, approuvées, en attente, rejetées
- **Filtres avancés** : Par caisse, catégorie, statut
- **Tableau des dépenses** : Vue complète avec actions
- **Modales** : Création et édition des dépenses

### Navigation

- Onglet dédié dans le menu principal
- Intégration avec le système de rapports existant
- Boutons d'action contextuels selon le statut

## 🔧 Développement technique

### API Endpoints

- `GET /api/depenses/` : Liste des dépenses
- `POST /api/depenses/` : Créer une dépense
- `PUT /api/depenses/{id}/` : Modifier une dépense
- `POST /api/depenses/{id}/approuver/` : Approuver une dépense
- `POST /api/depenses/{id}/rejeter/` : Rejeter une dépense
- `GET /api/depenses/stats/` : Statistiques des dépenses

### Sérialiseurs

- **DepenseSerializer** : Sérialiseur complet pour les opérations CRUD
- **DepenseListSerializer** : Sérialiseur simplifié pour les listes

### Permissions

- **Agents** : Accès aux dépenses de leurs caisses
- **Administrateurs** : Accès complet à toutes les dépenses

## 📈 Rapports et exports

### Types de rapports

1. **Rapport général des dépenses** : Vue d'ensemble complète
2. **Rapport par caisse** : Dépenses d'une caisse spécifique
3. **Rapport par catégorie** : Analyse par type de dépense
4. **Rapport par période** : Dépenses sur une période donnée

### Formats d'export

- **PDF** : Rapports formatés et imprimables
- **Excel** : Données structurées pour analyse
- **CSV** : Export simple pour traitement externe

## 🧪 Tests et données d'exemple

### Commande de test

```bash
python manage.py seed_depenses --nombre 20
```

Cette commande crée 20 dépenses d'exemple avec des données réalistes pour tester le système.

### Scénarios de test

1. **Création de dépense** : Vérifier la validation des champs
2. **Approbation** : Tester l'approbation avec solde suffisant
3. **Rejet** : Tester le rejet avec motif
4. **Filtrage** : Vérifier les filtres par catégorie et statut
5. **Calculs** : Vérifier l'exactitude des statistiques

## 🚨 Dépannage

### Problèmes courants

1. **Erreur de solde insuffisant** : Vérifier les cotisations de solidarité et pénalités
2. **Responsable non trouvé** : S'assurer que le membre appartient à la caisse
3. **Validation échouée** : Vérifier que tous les champs obligatoires sont remplis

### Logs et débogage

- Les erreurs sont loggées dans la console du navigateur
- Les actions sont tracées dans les journaux Django
- Utiliser les outils de développement du navigateur pour déboguer

## 🔮 Évolutions futures

### Fonctionnalités prévues

1. **Notifications** : Alertes pour dépenses en attente
2. **Workflow** : Processus d'approbation multi-niveaux
3. **Budgets** : Gestion de budgets par catégorie
4. **Pièces jointes** : Support des justificatifs numériques
5. **Approbation en lot** : Traitement de plusieurs dépenses

### Intégrations

- **SMS/Email** : Notifications automatiques
- **Signature électronique** : Approbation sécurisée
- **Synchronisation** : Intégration avec d'autres systèmes

---

## 📞 Support

Pour toute question ou problème avec le système de dépenses, contactez l'équipe de développement ou consultez la documentation technique.
