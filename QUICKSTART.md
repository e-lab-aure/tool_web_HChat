# HChat - Démarrage Rapide avec Podman

## Installation en 3 minutes

### 1. Avec le script `deploy.sh` (Recommandé)

```bash
# Rendre le script exécutable
chmod +x deploy.sh

# Construire et démarrer
./deploy.sh start

# Afficher les logs
./deploy.sh logs

# Accéder à HChat
# http://localhost:8080
```

### 2. Avec Podman directement

```bash
# Construire l'image
podman build -t hchat:latest .

# Démarrer le conteneur
podman run -d \
  --name hchat \
  -p 8080:8080 \
  -e SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))") \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/data:/app/data \
  --restart unless-stopped \
  hchat:latest

# Vérifier que c'est lancé
podman logs hchat
```

### 3. Avec docker-compose

```bash
# Générer une clé secrète
export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# Lancer
docker-compose up -d

# Logs
docker-compose logs -f hchat
```

---

## Commandes Utiles

### Voir les logs
```bash
./deploy.sh logs
podman logs -f hchat
docker-compose logs -f hchat
```

### Arrêter
```bash
./deploy.sh stop
podman stop hchat
docker-compose down
```

### Redémarrer
```bash
./deploy.sh restart
podman restart hchat
docker-compose restart hchat
```

### Supprimer complètement
```bash
./deploy.sh remove
podman rm hchat
docker-compose down -v
```

---

## Configuration

### Port personnalisé
```bash
# Avec deploy.sh
PORT=3000 ./deploy.sh start

# Avec podman
podman run -d -p 3000:8080 hchat:latest

# Avec docker-compose
# Éditer docker-compose.yml et changer les ports
```

### Clé secrète
```bash
# Générer une clé forte
python3 -c "import secrets; print(secrets.token_hex(32))"

# Utiliser avec deploy.sh
SECRET_KEY="..." ./deploy.sh start

# Ou la mettre dans .env.production
# Puis charger avec: export $(cat .env.production | xargs)
```

---

## Vérification

```bash
# HChat est accessible à
http://localhost:8080

# Vérifier la santé du conteneur
podman inspect hchat | grep -A 5 "Health"

# Voir les processus dans le conteneur
podman top hchat

# Accéder au shell du conteneur
podman exec -it hchat /bin/bash
```

---

## Dépannage

### Le conteneur s'arrête immédiatement
```bash
podman logs hchat
```
Vérifier les erreurs dans les logs.

### Port déjà utilisé
```bash
# Utiliser un autre port
PORT=3000 ./deploy.sh start
```

### Permission denied sur les volumes
```bash
chmod 777 uploads data chat.log
```

### Réinitialiser la base de données
```bash
rm -rf data/chat.db
podman restart hchat
```

---

## Documentation complète

Voir **DEPLOYMENT.md** pour une configuration avancée, proxy inverse, SSL, etc.
