## Git & GitHub - Commandes utiles (GestionCaisse)

### 1) Configuration initiale
```bash
git init -b main
git config user.name "Votre Nom"
git config user.email "vous@example.com"
git remote add origin https://github.com/DizeAnalytics/GestionCaisse.git
git add .
git commit -m "Initial commit"
git push -u origin main
```

### 2) Workflow quotidien
```bash
git status
git pull --rebase origin main
git checkout -b feature/ma-fonction
git add -A
git commit -m "feat: ajouter ma fonctionnalité"
git push -u origin feature/ma-fonction
# Ouvrir la Pull Request depuis GitHub, ou (si gh installé):
# gh pr create --fill --base main --head feature/ma-fonction
```

### 3) Tags & releases
```bash
git tag -a v1.0.1 -m "Version 1.0.1"
git push origin v1.0.1
# Avec GitHub CLI (optionnel):
# gh release create v1.0.1 --notes "Notes de version"
```

### 4) CI GitHub Actions
```bash
# Voir les exécutions:
gh run list
# Suivre la dernière exécution:
gh run watch --exit-status
# Voir les logs d'un run:
gh run view --log-failed
```

### 5) Secrets GitHub (Actions)
```bash
gh secret set DOCKER_REPO -b "docker.io/votreuser/caisses-femmes"
gh secret set DOCKER_USERNAME -b "votreuser"
gh secret set DOCKER_PASSWORD -b "votre-mot-de-passe-ou-token"
```

### 6) Historique & diff
```bash
git log --oneline --graph --decorate -n 20
git diff
git show HEAD~1
```

### 7) Corrections
```bash
git restore --staged .
git checkout -- .
git reset --hard HEAD
git revert <commit_sha>
```

### 8) Stash, merge, rebase
```bash
git stash push -m "wip"
git stash pop
git merge origin/main
git rebase origin/main
```

### 9) Maintenance
```bash
git gc --prune=now
git remote -v
git remote set-url origin https://github.com/DizeAnalytics/GestionCaisse.git
```

### 10) Windows (CRLF)
```bash
git config core.autocrlf true
```


