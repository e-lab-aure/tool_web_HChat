# HChat - Démarrage Rapide (Podman)

## Installation en 3 minutes

### Option 1: Avec le script `deploy.sh` (Recommandé)

```bash
chmod +x deploy.sh
./deploy.sh start
./deploy.sh logs
```

HChat accessible à: **http://localhost:8080**

---

### Option 2: Avec Podman directement

```bash
# Construire l'image
podman build -t hchat:latest .

# Lancer le conteneur
podman run -d \
  --name hchat \
  -p 8080:8080 \
  -e SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))") \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/data:/app/data \
  --restart unless-stopped \
  hchat:latest

# Vérifier
podman logs hchat
```

---

## Commandes Utiles

```bash
# Voir les logs
./deploy.sh logs
podman logs -f hchat

# Arrêter
./deploy.sh stop
podman stop hchat

# Redémarrer
./deploy.sh restart
podman restart hchat

# Supprimer
./deploy.sh remove
podman rm hchat
```

---

## Configuration

### Port personnalisé
```bash
PORT=3000 ./deploy.sh start
```

### Clé secrète
```bash
# Générer une clé forte
python3 -c "import secrets; print(secrets.token_hex(32))"

# Utiliser
SECRET_KEY="..." ./deploy.sh start
```

---

## Vérification

```bash
# Statut
podman ps | grep hchat

# Santé du conteneur
podman inspect hchat | grep -A 5 "Health"

# Processus dans le conteneur
podman top hchat

# Shell du conteneur
podman exec -it hchat /bin/bash
```

---

## Dépannage

```bash
# Conteneur s'arrête immédiatement
podman logs hchat

# Port en conflit
PORT=3000 ./deploy.sh start

# Permission denied sur volumes
chmod 777 uploads data

# Réinitialiser la base de données
rm -rf data/chat.db && podman restart hchat
```

---

Pour une configuration avancée, voir **DEPLOYMENT.md**
