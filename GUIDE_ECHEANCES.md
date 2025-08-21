# Guide d'Utilisation - Calcul Automatique des Échéances

## Vue d'ensemble

Le système de gestion des caisses a été enrichi avec un système automatique de calcul des échéances de remboursement pour les prêts. Cette fonctionnalité permet de :

1. **Calculer automatiquement les échéances** lors de l'octroi d'un prêt
2. **Suivre les échéances en retard** pour identifier les membres en difficulté
3. **Générer des rapports PDF** des échéances en retard
4. **Afficher les échéances** sur tous les PDF de prêts et remboursements

## Fonctionnalités Principales

### 1. Calcul Automatique des Échéances

#### Comment ça fonctionne :
- Lorsqu'un prêt est **octroyé** (statut passe à "EN_COURS"), le système calcule automatiquement toutes les échéances
- Le calcul prend en compte :
  - Le montant total à rembourser (principal + intérêts)
  - La durée du prêt en mois
  - La date de décaissement comme point de départ

#### Formule de calcul :
```
Montant par échéance = (Montant principal + Intérêts) / Durée en mois
Date de première échéance = Date de décaissement + 30 jours
```

#### Exemple :
- Prêt de 100,000 FCFA sur 6 mois avec 5% d'intérêt
- Total à rembourser : 105,000 FCFA
- Montant par échéance : 17,500 FCFA
- 6 échéances mensuelles à partir du mois suivant le décaissement

### 2. Suivi des Échéances en Retard

#### Détection automatique :
- Le système vérifie quotidiennement les échéances échues
- Une échéance est considérée en retard si :
  - La date d'échéance est dépassée
  - Le statut est "A_PAYER" ou "PARTIELLEMENT_PAYE"

#### Propriété `est_en_retard` :
- Chaque prêt a maintenant une propriété `est_en_retard`
- Retourne `true` si le prêt a des échéances en retard
- Utilisée pour l'affichage et les rapports

### 3. Méthodes Utiles du Modèle Pret

#### `calculer_echeances()`
```python
# Calcule et crée automatiquement toutes les échéances
echeances = pret.calculer_echeances()
```

#### `get_echeances_en_retard()`
```python
# Retourne les échéances en retard pour un prêt
echeances_retard = pret.get_echeances_en_retard()
```

#### `get_prochaine_echeance()`
```python
# Retourne la prochaine échéance à payer
prochaine = pret.get_prochaine_echeance()
```

## Interface Utilisateur

### 1. Bouton "Échéances en Retard"

Dans la section **Prêts** du dashboard, un nouveau bouton a été ajouté :
- **Icône** : ⚠️ (triangle d'avertissement)
- **Texte** : "Échéances en Retard"
- **Couleur** : Orange (btn-warning)
- **Fonction** : Génère un PDF des échéances en retard

### 2. Génération du PDF

#### Pour une caisse spécifique :
```
GET /gestion-caisses/api/caisses/{caisse_id}/echeances_retard_pdf/
```

#### Pour toutes les caisses (admin seulement) :
```
GET /gestion-caisses/api/caisses/echeances_retard_global_pdf/
```

## Contenu des PDF

### 1. PDF d'Octroi de Prêt

Le PDF d'octroi de prêt inclut maintenant :
- **Section "ÉCHÉANCES DE REMBOURSEMENT"**
- Tableau détaillé de toutes les échéances calculées
- Dates d'échéance et montants
- Statut de chaque échéance

### 2. PDF de Remboursement

Le PDF de remboursement inclut maintenant :
- **Section "ÉTAT DES ÉCHÉANCES"**
- Tableau de toutes les échéances avec statuts
- Résumé des échéances payées/en retard/à payer
- Prochaine échéance à payer

### 3. PDF des Échéances en Retard

Nouveau PDF spécialisé contenant :
- **Statistiques générales** : nombre d'échéances en retard, montant total, prêts concernés
- **Détail des échéances** : membre, prêt, date, jours de retard, montant
- **Recommandations** : actions à entreprendre
- **Signatures** : Président Général et Présidente de caisse

## Utilisation Pratique

### 1. Octroi d'un Prêt

1. Créer un prêt avec montant, durée et taux d'intérêt
2. Valider le prêt (statut "VALIDE")
3. **Octroyer le prêt** (statut "EN_COURS")
4. Les échéances sont automatiquement calculées et créées

### 2. Suivi des Retards

1. Cliquer sur le bouton "Échéances en Retard"
2. Le PDF généré montre :
   - Membres en retard
   - Montants dus
   - Jours de retard
   - Actions recommandées

### 3. Remboursements

1. Enregistrer un remboursement
2. Le système met à jour automatiquement :
   - Le montant remboursé du prêt
   - Le statut des échéances concernées
   - La propriété `est_en_retard`

## Avantages du Système

### 1. Automatisation
- Calcul automatique des échéances
- Détection automatique des retards
- Mise à jour automatique des statuts

### 2. Transparence
- Échéances visibles sur tous les PDF
- Rapports détaillés des retards
- Suivi en temps réel

### 3. Gestion Proactive
- Identification rapide des membres en difficulté
- Recommandations d'actions
- Prévention des retards

### 4. Conformité
- Documents officiels avec échéances
- Traçabilité complète
- Signatures numériques

## Maintenance

### 1. Vérification Quotidienne

Le système vérifie automatiquement :
- Les échéances échues
- Les prêts en retard
- Les statistiques de remboursement

### 2. Rapports Réguliers

Générer régulièrement :
- Rapport des échéances en retard
- Suivi des remboursements
- Statistiques de performance

### 3. Actions Correctives

En cas d'échéances en retard :
1. Contacter le membre
2. Proposer un plan de remboursement
3. Suivre les paiements
4. Mettre à jour les statuts

## Support Technique

### En cas de problème :

1. **Échéances non calculées** : Vérifier que le prêt a été octroyé
2. **PDF non généré** : Vérifier les permissions utilisateur
3. **Statuts incorrects** : Vérifier les remboursements enregistrés

### Logs et Debugging :

- Les calculs d'échéances sont loggés dans les logs Django
- Les erreurs de génération PDF sont affichées dans la console
- Les actions utilisateur sont tracées dans les logs d'audit

---

**Note** : Ce système améliore significativement la gestion des prêts en permettant un suivi précis des échéances et une identification proactive des retards de remboursement.
