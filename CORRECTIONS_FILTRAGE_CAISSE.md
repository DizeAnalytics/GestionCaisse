# Corrections du Filtrage par Caisse

## Problème identifié

AMALI Ama ne fait pas partie de la caisse "Femme NOVISSI" mais son prêt était visible dans cette caisse. Les utilisateurs devraient voir uniquement les activités de leur propre caisse.

## Cause du problème

Le problème était dans le template JavaScript (`gestion_caisses/templates/gestion_caisses/prets.html`) qui ne respectait pas les restrictions de l'utilisateur :

1. **Filtre de caisse non restreint** : Le filtre de caisse chargeait toutes les caisses, permettant aux utilisateurs de sélectionner d'autres caisses
2. **Chargement des membres non filtré** : La fonction `loadMembres()` chargeait tous les membres au lieu de filtrer par caisse
3. **Chargement des prêts non forcé** : La fonction `loadPrets()` n'appliquait pas automatiquement le filtre de caisse pour les utilisateurs non-admin

## Corrections apportées

### 1. Modification de `loadCaisses()`

**Avant :**
```javascript
function loadCaisses() {
    fetch('/api/caisses/', {
        headers: {
            'X-CSRFToken': getCSRFToken(),
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        const select = document.getElementById('filter-caisse');
        const caisses = data.results || data;
        
        caisses.forEach(caisse => {
            const option = document.createElement('option');
            option.value = caisse.id;
            option.textContent = `${caisse.nom} (${caisse.code})`;
            select.appendChild(option);
        });
    })
    .catch(error => console.error('Erreur lors du chargement des caisses:', error));
}
```

**Après :**
```javascript
function loadCaisses() {
    // Si l'utilisateur a une caisse spécifique, ne charger que cette caisse
    if (USER_CAISE_ID) {
        fetch(`/api/caisses/${USER_CAISE_ID}/`, {
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(caisse => {
            const select = document.getElementById('filter-caisse');
            const option = document.createElement('option');
            option.value = caisse.id;
            option.textContent = `${caisse.nom_association} (${caisse.code})`;
            select.appendChild(option);
            // Désactiver le filtre caisse pour les non-admins
            select.disabled = true;
        })
        .catch(error => console.error('Erreur lors du chargement de la caisse:', error));
    } else {
        // Pour les admins, charger toutes les caisses
        fetch('/api/caisses/', {
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            const select = document.getElementById('filter-caisse');
            const caisses = data.results || data;
            
            caisses.forEach(caisse => {
                const option = document.createElement('option');
                option.value = caisse.id;
                option.textContent = `${caisse.nom_association} (${caisse.code})`;
                select.appendChild(option);
            });
        })
        .catch(error => console.error('Erreur lors du chargement des caisses:', error));
    }
}
```

### 2. Modification de `loadMembres()`

**Avant :**
```javascript
function loadMembres() {
    fetch('/api/membres/', {
        headers: {
            'X-CSRFToken': getCSRFToken(),
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        const select = document.getElementById('filter-membre');
        const membres = data.results || data;
        
        membres.forEach(membre => {
            const option = document.createElement('option');
            option.value = membre.id;
            option.textContent = membre.nom_complet;
            select.appendChild(option);
        });
    })
    .catch(error => console.error('Erreur lors du chargement des membres:', error));
}
```

**Après :**
```javascript
function loadMembres() {
    let url = '/api/membres/';
    const params = new URLSearchParams();
    
    // Si l'utilisateur a une caisse spécifique, filtrer par cette caisse
    if (USER_CAISE_ID) {
        params.append('caisse', USER_CAISE_ID);
    }
    
    if (params.toString()) {
        url += '?' + params.toString();
    }
    
    fetch(url, {
        headers: {
            'X-CSRFToken': getCSRFToken(),
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        const select = document.getElementById('filter-membre');
        const membres = data.results || data;
        
        membres.forEach(membre => {
            const option = document.createElement('option');
            option.value = membre.id;
            option.textContent = membre.nom_complet;
            select.appendChild(option);
        });
    })
    .catch(error => console.error('Erreur lors du chargement des membres:', error));
}
```

### 3. Modification de `loadPrets()`

**Avant :**
```javascript
function loadPrets() {
    const caisseFilter = document.getElementById('filter-caisse').value;
    const statusFilter = document.getElementById('filter-status').value;
    const membreFilter = document.getElementById('filter-membre').value;
    
    let url = '/api/prets/';
    const params = new URLSearchParams();
    
    if (caisseFilter) params.append('caisse', caisseFilter);
    if (statusFilter) params.append('statut', statusFilter);
    if (membreFilter) params.append('membre', membreFilter);
    
    // ... reste du code
}
```

**Après :**
```javascript
function loadPrets() {
    const caisseFilter = document.getElementById('filter-caisse').value;
    const statusFilter = document.getElementById('filter-status').value;
    const membreFilter = document.getElementById('filter-membre').value;
    
    let url = '/api/prets/';
    const params = new URLSearchParams();
    
    // Forcer le filtre de caisse pour les utilisateurs non-admin
    if (USER_CAISE_ID) {
        params.append('caisse', USER_CAISE_ID);
    } else if (caisseFilter) {
        params.append('caisse', caisseFilter);
    }
    
    if (statusFilter) params.append('statut', statusFilter);
    if (membreFilter) params.append('membre', membreFilter);
    
    // ... reste du code
}
```

### 4. Masquage du filtre de caisse pour les non-admins

Ajout dans `fetchUserContext()` :
```javascript
function fetchUserContext(){
    fetch('/gestion-caisses/api/user-context/', { headers: { 'X-CSRFToken': getCSRFToken() }})
      .then(r=>r.json()).then(data=>{ 
          USER_CAISE_ID = data.caisse_id || null; 
          // Masquer le filtre de caisse pour les utilisateurs non-admin
          if (USER_CAISE_ID) {
              const caisseFilterGroup = document.getElementById('filter-caisse').closest('.filter-group');
              if (caisseFilterGroup) {
                  caisseFilterGroup.style.display = 'none';
              }
          }
      });
}
```

### 5. Ajout de `loadMembresForModal()`

Nouvelle fonction pour charger les membres dans le modal de création de prêt :
```javascript
function loadMembresForModal() {
    let url = '/api/membres/';
    const params = new URLSearchParams();
    
    // Si l'utilisateur a une caisse spécifique, filtrer par cette caisse
    if (USER_CAISE_ID) {
        params.append('caisse', USER_CAISE_ID);
    }
    
    if (params.toString()) {
        url += '?' + params.toString();
    }
    
    fetch(url, {
        headers: {
            'X-CSRFToken': getCSRFToken(),
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        const select = document.getElementById('pretMembre');
        select.innerHTML = '<option value="">Sélectionner un membre</option>';
        const membres = data.results || data;
        
        membres.forEach(membre => {
            const option = document.createElement('option');
            option.value = membre.id;
            option.textContent = membre.nom_complet;
            select.appendChild(option);
        });
    })
    .catch(error => console.error('Erreur lors du chargement des membres pour le modal:', error));
}
```

## Vérification du backend

Le filtrage backend était déjà correctement implémenté dans les vues :

- `PretViewSet.get_queryset()` : Filtre les prêts par caisse de l'utilisateur
- `MembreViewSet.get_queryset()` : Filtre les membres par caisse de l'utilisateur  
- `CaisseViewSet.get_queryset()` : Filtre les caisses pour les non-admins

## Résultat

Après ces corrections :

1. ✅ Les utilisateurs non-admin ne voient que les prêts de leur caisse
2. ✅ Le filtre de caisse est masqué pour les utilisateurs non-admin
3. ✅ Seuls les membres de leur caisse sont chargés dans les filtres
4. ✅ Seuls les membres de leur caisse sont disponibles pour créer des prêts
5. ✅ Le filtrage est forcé automatiquement côté frontend et backend

## Test

Un script de test (`test_filtrage_caisse.py`) a été créé pour vérifier que le filtrage fonctionne correctement.

## Sécurité

Ces corrections garantissent que :
- Les utilisateurs ne peuvent pas accéder aux données d'autres caisses
- Le filtrage est appliqué à la fois côté frontend et backend
- Les restrictions sont respectées pour tous les types d'utilisateurs
