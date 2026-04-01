# HChat - Démarrage Rapide (Podman)

## Installation en 3 minutes

### Avec le script `deploy.sh`

```bash
# Depuis le répertoire du projet
cd /opt/tool_web_HChat
chmod +x deploy.sh
./deploy.sh
```

HChat accessible à: **http://localhost:8080**

---

### Ou avec Podman directement

```bash
# Construire l'image
podman build -t hchat:latest -f Containerfile .

# Lancer le conteneur
podman run -d \
  --replace \
  --name hchat \
  -p 8080:8080 \
  --env-file .env \
  -v /opt/tool_web_HChat/data:/app/data:z \
  -v /opt/tool_web_HChat/uploads:/app/uploads:z \
  --restart unless-stopped \
  hchat:latest

# Vérifier
podman logs -f hchat
```

---

## Commandes Utiles

```bash
# Voir les logs
podman logs -f hchat

# Arrêter
podman stop hchat
podman rm hchat

# Statut
podman ps | grep hchat

# Shell du conteneur
podman exec -it hchat /bin/bash
```

---

## Configuration

### Port personnalisé
```bash
PORT=3000 ./deploy.sh
```

### Variables du fichier `.env`
```bash
cat > .env << 'EOF'
PORT=8080
HOST=0.0.0.0
SECRET_KEY=votre_cle_ici
MAX_UPLOAD_SIZE_MB=10
ROOM_EXPIRY_HOURS=24
LOG_LEVEL=INFO
EOF
```

---

Pour une configuration avancée, voir **DEPLOYMENT.md**
