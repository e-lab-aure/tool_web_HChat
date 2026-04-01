# Déploiement HChat en Production (Podman)

## Prérequis

- **Podman** 4.0+
- Au minimum 512 MB de RAM disponible
- Port 8080 libre (ou autre port de votre choix)
- Python 3.11+ (pour générer les clés secrètes localement)

## Architecture

Le projet utilise **Containerfile** (best practice Podman) basé sur `python:3.11-slim`:
- Image légère (~200 MB)
- Healthcheck intégré
- Support des volumes persistants pour `data/` et `uploads/`

---

## Installation Serveur

### 1. Cloner le projet

```bash
git clone <repo> /opt/tool_web_HChat
cd /opt/tool_web_HChat
```

### 2. Générer une clé secrète

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Créer `.env`

```bash
cat > .env << 'EOF'
PORT=8080
HOST=0.0.0.0
APP_NAME=HChat
SECRET_KEY=<COLLEZ_VOTRE_CLE_ICI>
MAX_UPLOAD_SIZE_MB=10
MAX_MESSAGE_SIZE_KB=64
MAX_HISTORY=100
ROOM_EXPIRY_HOURS=24
SESSION_EXPIRY_HOURS=8
LOG_LEVEL=INFO
EOF
```

### 4. Construire et lancer

```bash
chmod +x deploy.sh
./deploy.sh
```

HChat est accessible à: **http://your-server:8080**

---

## Configuration Avancée

### Personnaliser le port

```bash
PORT=3000 ./deploy.sh
```

### Limiter la taille des uploads

Modifier `.env`:

```env
MAX_UPLOAD_SIZE_MB=50
```

Puis relancer:

```bash
./deploy.sh
```

### Persister les données

Les volumes sont montés par défaut:
- `/opt/tool_web_HChat/data` → base de données SQLite
- `/opt/tool_web_HChat/uploads` → fichiers uploadés

Les logs applicatif sont visibles via:

```bash
podman logs -f hchat
```

---

## Commandes Podman

```bash
# Arrêter
podman stop hchat
podman rm hchat

# Redémarrer
./deploy.sh

# Voir les logs
podman logs -f hchat

# Statut
podman ps | grep hchat

# Santé du pod
podman inspect hchat --format='{{.State.Health.Status}}'
```

---

## Proxy Inverse (Nginx)

Pour exposer derrière un reverse proxy avec SSL/TLS:

```nginx
server {
    listen 443 ssl http2;
    server_name hchat.example.com;
    
    ssl_certificate /etc/ssl/certs/cert.pem;
    ssl_certificate_key /etc/ssl/private/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Dépannage

### Le pod s'arrête immédiatement

```bash
podman logs hchat
```

Vérifier les messages d'erreur.

### Port déjà utilisé

```bash
lsof -i :8080
# ou
PORT=3000 ./deploy.sh
```

### Reset base de données

```bash
rm -f /opt/tool_web_HChat/data/chat.db
./deploy.sh
```

---

## Backup des données

```bash
tar czf hchat-backup-$(date +%Y%m%d).tar.gz \
  /opt/tool_web_HChat/data \
  /opt/tool_web_HChat/uploads
```
