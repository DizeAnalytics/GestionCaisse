# Guide d’utilisation – Gestion des Caisses

Version: 1.0
Dernière mise à jour: 2025-09-16

## 1. Objectif du guide
Ce document décrit le fonctionnement de l’application et fournit des procédures pas-à-pas pour les utilisateurs et administrateurs.

## 2. Aperçu
- Membres, Caisses, Cotisations, Prêts, Dépenses
- Rapports (activité, réalisme, états généraux) et impressions PDF
- Tableau de bord et administration

## 3. Installation rapide
- Python 3.10+, Git
- pip install -r requirements.txt
- python manage.py migrate && python manage.py runserver
- Accès: http://127.0.0.1:8000

## 4. Procédures clés
- Ajouter un membre: Menu Membres > Nouveau
- Enregistrer une cotisation: fiche membre > Cotisation > Nouvelle
- Créer un prêt: Menu Prêts > Nouveau puis suivre les échéances
- Enregistrer une dépense: Menu Dépenses > Nouvelle
- Générer un rapport: Menu Rapports > choisir type > Générer

## 5. Dépannage
- Migrations: python manage.py migrate
- Accès refusé: vérifier permissions
