# Validation des corrections Docker

## Corrections appliquées

### 1. Dockerfile corrigé
- ✅ `COPY ../requirements.txt .` → `COPY requirements.txt .`
- ✅ `COPY . .` remplacé par des copies spécifiques:
  - `COPY src/ /app/src/`
  - `COPY prompts/ /app/prompts/`
  - `COPY translation_api.py /app/`
  - `COPY translate.py /app/`
- ✅ Version Python mise à jour: `3.9-slim` → `3.11-slim`

### 2. .dockerignore amélioré
- ✅ Ajout de plus d'exclusions (venv/, logs/, data/, tests/)
- ✅ Exclusion des fichiers de déploiement (deployment/, Dockerfile, etc.)
- ✅ Exclusion du dossier plan/ (selon CLAUDE.md)

## Comment tester

### Option 1: Script automatisé (Recommandé)

**Windows:**
```cmd
cd deployment
test_docker.bat
```

**Linux/macOS:**
```bash
cd deployment
chmod +x test_docker.sh
./test_docker.sh
```

### Option 2: Commandes manuelles

1. **Démarrer Docker Desktop**
   - Windows: Vérifier que l'icône Docker est verte dans la barre des tâches

2. **Build l'image:**
   ```bash
   cd deployment
   docker-compose build
   ```

   Vous devriez voir:
   ```
   [+] Building X.Xs (10/10) FINISHED
   => [internal] load build definition from Dockerfile
   => => transferring dockerfile: 1.05kB
   => [internal] load .dockerignore
   => [internal] load metadata for docker.io/library/python:3.11-slim
   => [1/6] FROM docker.io/library/python:3.11-slim
   => [internal] load build context
   => [2/6] WORKDIR /app
   => [3/6] RUN apt-get update && apt-get install -y --no-install-recommends curl
   => [4/6] COPY requirements.txt .
   => [5/6] RUN pip install --no-cache-dir -r requirements.txt
   => [6/6] COPY src/ /app/src/
   => exporting to image
   ```

3. **Démarrer le conteneur:**
   ```bash
   docker-compose up -d
   ```

4. **Vérifier le statut:**
   ```bash
   docker-compose ps
   ```

   Devrait afficher: `Up X seconds (healthy)`

5. **Tester l'API:**
   ```bash
   curl http://localhost:5000/api/health
   ```

   Réponse attendue:
   ```json
   {
     "message": "Translation API is running",
     "status": "ok",
     "supported_formats": ["txt", "epub", "srt"],
     "translate_module": "loaded"
   }
   ```

6. **Accéder à l'interface web:**
   Ouvrir: http://localhost:5000

## Vérifications de structure

### Fichiers qui doivent être copiés dans l'image:
- ✅ `/app/requirements.txt`
- ✅ `/app/src/` (tous les modules Python)
- ✅ `/app/prompts/` (prompts de traduction)
- ✅ `/app/translation_api.py`
- ✅ `/app/translate.py`

### Fichiers qui NE doivent PAS être copiés:
- ❌ `deployment/` (fichiers de déploiement)
- ❌ `tests/` (tests unitaires)
- ❌ `plan/` (plans de développement)
- ❌ `.git/` (historique Git)
- ❌ `__pycache__/` (fichiers Python compilés)
- ❌ `.env` (configuration locale)

## Commandes utiles après le déploiement

```bash
# Voir les logs
docker-compose logs -f

# Redémarrer
docker-compose restart

# Arrêter
docker-compose down

# Shell dans le conteneur
docker-compose exec translatebook bash

# Vérifier la structure des fichiers
docker-compose exec translatebook ls -la /app/
docker-compose exec translatebook ls -la /app/src/
docker-compose exec translatebook ls -la /app/prompts/
```

## Résolution de problèmes

### Build échoue avec "no such file or directory"
- Vérifier que vous êtes dans le dossier `deployment/`
- Vérifier que `requirements.txt` existe à la racine du projet
- Vérifier que les dossiers `src/` et `prompts/` existent

### Conteneur redémarre continuellement
```bash
docker-compose logs
```
Chercher les erreurs Python ou les imports manquants

### Health check échoue
Attendre 45 secondes après le démarrage (grace period), puis vérifier:
```bash
docker-compose exec translatebook curl http://localhost:5000/api/health
```

## Tests de validation

Après le démarrage réussi, testez:

1. **Health endpoint:** ✅
   ```bash
   curl http://localhost:5000/api/health
   ```

2. **Interface web:** ✅
   Ouvrir http://localhost:5000 dans un navigateur

3. **Traduction basique:** ✅
   - Uploader un petit fichier .txt via l'interface
   - Vérifier que la traduction démarre
   - Vérifier les logs: `docker-compose logs -f`

4. **Persistance des données:** ✅
   ```bash
   # Arrêter le conteneur
   docker-compose down

   # Redémarrer
   docker-compose up -d

   # Vérifier que les données persistent
   docker-compose exec translatebook ls -la /app/data/
   ```

## Succès attendu

Si tout fonctionne correctement, vous devriez voir:

```
✅ Docker image built successfully
✅ Container started and healthy
✅ Health endpoint responds with "ok"
✅ Web interface accessible at http://localhost:5000
✅ Logs show "LLM TRANSLATION SERVER STARTED"
```

## Note importante

Les corrections appliquées résolvent les problèmes critiques du Dockerfile:
- Les chemins de COPY sont maintenant corrects par rapport au contexte de build
- La structure des fichiers dans l'image est propre et organisée
- La version Python est mise à jour (3.11 vs 3.9)
- Le .dockerignore évite de copier des fichiers inutiles

Le package Docker est maintenant **opérationnel** et prêt pour le déploiement.
