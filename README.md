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

**Avec script de lancement rapide:**

```bash
# Une seule fois: copier dans le home
cp run_HChat.sh ~/ && chmod +x ~/run_HChat.sh

# Puis lancer (mise a jour Git + demarrage)
~/run_HChat.sh
```

**Ou manuellement:**

```bash
chmod +x deploy.sh
./deploy.sh start
# → http://your-server:8080
```

---

## 📋 Installation Serveur (Rapide)

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
ROOM_EXPIRY_HOURS=24
LOG_LEVEL=INFO
EOF
```

### 4. Installer le lanceur dans le home

```bash
cp run_HChat.sh ~/ && chmod +x ~/run_HChat.sh
```

### 5. Lancer (mise à jour + démarrage)

```bash
~/run_HChat.sh          # Ou simplement: ~/run_HChat.sh pull
```

HChat est accessible à: **http://your-server:8080**

---

## 🔧 Utilisation du Lanceur

```bash
~/run_HChat.sh              # Mise a jour Git + demarrage
~/run_HChat.sh logs         # Voir les logs en direct
~/run_HChat.sh stop         # Arreter le pod
~/run_HChat.sh help         # Afficher l'aide
```

---

## 🔧 Commandes Directes

Pour lancer directement depuis le répertoire du projet:

```bash
cd /opt/tool_web_HChat

# Construire et lancer
./deploy.sh

# Ou avec variables d'environnement
PORT=3000 ./deploy.sh

# Voir les logs
podman logs -f hchat

# Arrêter
podman stop hchat
podman rm hchat
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
├── deploy.sh           # Script de gestion Podman
├── run_HChat.sh        # Lanceur rapide (copier dans ~/)
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

    # Limite de taille des uploads - doit correspondre a MAX_UPLOAD_SIZE_MB dans .env
    # Nginx rejette en amont ; l'app retourne une erreur JSON propre si Nginx laisse passer
    client_max_body_size 2048m;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts pour les gros fichiers (upload/download de plusieurs Go)
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }
}
```

### Limite d'upload : aligner Nginx et l'application

Les deux couches doivent avoir la meme valeur pour un comportement coherent :

| Couche | Parametre | Effet si depassé |
|--------|-----------|-----------------|
| Nginx | `client_max_body_size` | 413 brut, avant que l'app soit sollicitee |
| App | `MAX_UPLOAD_SIZE_MB` dans `.env` | 413 JSON avec message lisible cote client |

Configurer les deux a la meme valeur (ex: 2048 Mo) :

```bash
# .env
MAX_UPLOAD_SIZE_MB=2048
```

```nginx
# Nginx
client_max_body_size 2048m;
```

> **Ne pas mettre `0` (illimite) en production** : sans limite, un upload malveillant
> peut saturer le disque ou la memoire. Choisir une valeur adaptee a l'usage.

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
~/run_HChat.sh logs         # Voir les logs

# Port en conflit
PORT=3000 ./deploy.sh       # Utiliser un autre port

# Permission denied sur les volumes
chmod 755 /opt/tool_web_HChat/data
chmod 755 /opt/tool_web_HChat/uploads

# Reset base de données
rm -f /opt/tool_web_HChat/data/chat.db
~/run_HChat.sh              # Redémarrer
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
