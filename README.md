# HChat - Application de Chat Chiffré E2E

> Communication sécurisée, messages avec mise en forme riche, chiffrement de bout en bout, déploiement Podman.

## 🔒 Caractéristiques

- **Chiffrement E2E** — Web Crypto API (PBKDF2 → AES-GCM 256)
- **Rooms éphémères** — Identifiants mémorables (4 mots français), auto-destruction
- **Mise en forme riche** — Copier-coller HTML préservé (gras, italique, listes, liens, etc.)
- **Fichiers sécurisés** — Upload chiffré E2E, 50+ formats autorisés
- **Base de données intégrée** — SQLite, 0 dépendance externe
- **Déploiement Podman** — Containerisé, production-ready, volumes persistants

---

## 🚀 Démarrage

### Développement local

```bash
pip install -r requirements.txt
python server.py
# → http://localhost:5000
```

### Production (Podman) - Recommandé

```bash
chmod +x deploy.sh
./deploy.sh start
# → http://your-server:8080
```

---

## 📋 Configuration sur Serveur

### 1. Prérequis

```bash
podman --version  # Doit être 4.0+
mkdir -p uploads data
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
ROOM_EXPIRY_HOURS=24
LOG_LEVEL=INFO
EOF
```

### 4. Lancer le Pod

```bash
# Avec le script (recommandé)
./deploy.sh start

# Ou manuellement
podman build -t hchat:latest .
podman run -d \
  --name hchat \
  -p 8080:8080 \
  --env-file .env \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/data:/app/data \
  --restart unless-stopped \
  hchat:latest
```

### 5. Vérifier le statut

```bash
podman logs -f hchat
# → HChat doit être accessible à http://your-server:8080
```

---

## 🔧 Commandes Utiles

```bash
./deploy.sh start           # Démarrer
./deploy.sh stop            # Arrêter
./deploy.sh restart         # Redémarrer
./deploy.sh logs            # Voir les logs
./deploy.sh remove          # Supprimer le conteneur

PORT=3000 ./deploy.sh start # Port personnalisé
SECRET_KEY="..." ./deploy.sh start
```

---

## 🔐 Architecture Sécurité

```
Client A                                    Client B
   │                                           │
   ├─ Mot de passe                            ├─ Même mot de passe
   │  ↓                                       │  ↓
   ├─ PBKDF2 → AES-GCM 256                   ├─ PBKDF2 → AES-GCM 256
   │  ↓                                       │  ↓
   └─ Ciphertext UNIQUEMENT                  └─ Ciphertext UNIQUEMENT
      ↓                                          ↓
      └─────────────────┬──────────────────────┘
                        │
                    Serveur
              (stocke le ciphertext)
                   (zéro-knowledge)
```

- Le serveur ne connaît **jamais** le mot de passe
- Seuls les clients avec le mot de passe peuvent déchiffrer
- Les fichiers sont aussi chiffrés E2E

---

## 📦 Structure

```
tool_HChat/
├── server.py           # Point d'entrée
├── app.py              # Factory aiohttp
├── config.py           # Configuration
├── state.py            # État global
├── Containerfile       # Image Podman (best practice)
├── docker-compose.yml  # Compose (podman-compose)
├── deploy.sh           # Script de gestion
├── requirements.txt    # Dépendances
├── handlers/           # Handlers HTTP/WS
├── utils/              # Utilitaires (DB, logs, cleanup)
├── static/             # Fichiers statiques
│   ├── room.html       # Interface utilisateur
│   └── crypto.js       # Chiffrement client (Web Crypto API)
└── README.md           # Ce fichier
```

---

## 🌐 Proxy Inverse (Nginx)

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

## 📊 Monitoring

```bash
# Santé du Pod
podman inspect hchat --format='{{.State.Health.Status}}'

# Ressources utilisées
podman stats hchat

# Logs avec tail
podman logs --tail 50 -f hchat

# Backup des données
tar czf hchat-backup-$(date +%Y%m%d).tar.gz uploads/ data/
```

---

## 🐛 Dépannage

```bash
# Pod s'arrête immédiatement
podman logs hchat

# Port en conflit
PORT=3000 ./deploy.sh start

# Permission denied
chmod 755 uploads data

# Reset base de données
rm -f data/chat.db && podman restart hchat
```

---

## 📖 Documentation

- **[QUICKSTART.md](QUICKSTART.md)** — Démarrage en 3 minutes
- **[DEPLOYMENT.md](DEPLOYMENT.md)** — Configuration avancée

---

## ✅ Checklist Production

- [ ] Générer une clé `SECRET_KEY` aléatoire forte
- [ ] Configurer un reverse proxy (Nginx) avec SSL/TLS
- [ ] Configurer le firewall (ouvrir que le port 443 public)
- [ ] Mettre en place des sauvegardes régulières
- [ ] Configurer la surveillance des logs
- [ ] Tester l'accès depuis un client externe
