# Déploiement HChat avec Podman

## Prérequis

- Podman ou Docker installé
- Au minimum 512 MB de RAM disponible
- Port 8080 libre (ou autre port de votre choix)

## Installation rapide (Podman)

### 1. Cloner ou télécharger HChat

```bash
cd /path/to/hchat
```

### 2. Générer une clé secrète (recommandé)

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copier la valeur générée.

### 3. Créer le conteneur

```bash
podman build -t hchat:latest .
```

### 4. Lancer le conteneur

**Avec une clé secrète forte:**

```bash
podman run -d \
  --name hchat \
  -p 8080:8080 \
  -e SECRET_KEY="votre_cle_generee_ici" \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/chat.log:/app/chat.log \
  --restart unless-stopped \
  hchat:latest
```

**Ou simplement (développement):**

```bash
podman run -d \
  --name hchat \
  -p 8080:8080 \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/data:/app/data \
  --restart unless-stopped \
  hchat:latest
```

### 5. Vérifier que c'est lancé

```bash
podman ps | grep hchat
podman logs hchat
```

HChat doit être disponible à: **http://your-server:8080**

---

## Utiliser Docker Compose (optionnel, plus simple)

Si vous préférez utiliser `docker-compose` (ou `podman-compose`):

### 1. Générer une clé secrète

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Créer un fichier `.env.prod`

```bash
cp .env.example .env.prod
```

Éditer `.env.prod` et remplacer:

```env
SECRET_KEY=votre_cle_generee_ici
PORT=8080
HOST=0.0.0.0
```

### 3. Lancer avec compose

```bash
docker-compose up -d
```

Ou avec Podman:

```bash
podman-compose up -d
```

### 4. Vérifier

```bash
docker-compose ps
docker-compose logs -f hchat
```

---

## Configuration avancée

### Personnaliser le port

Modifier le `docker-compose.yml`:

```yaml
ports:
  - "3000:8080"  # Accès via port 3000
```

Ou en ligne de commande:

```bash
podman run -d -p 3000:8080 hchat:latest
```

### Limiter la taille des uploads

Dans `docker-compose.yml`:

```yaml
environment:
  MAX_UPLOAD_SIZE_MB: 50
```

### Persister les données

Les volumes sont configurés par défaut:
- `./uploads` → fichiers uploadés
- `./data` → base de données SQLite
- `./chat.log` → logs applicatif

### Logs en temps réel

```bash
podman logs -f hchat
```

---

## Arrêter le conteneur

```bash
podman stop hchat
podman rm hchat
```

Ou avec compose:

```bash
docker-compose down
```

---

## Troubleshooting

### Le conteneur s'arrête aussitôt après le lancement

```bash
podman logs hchat
```

Vérifier les erreurs. Généralement: port en conflit ou répertoires non accessibles.

### Base de données verrouillée

```bash
podman exec hchat rm -f /app/data/chat.db
podman restart hchat
```

Cela supprime la DB et force une recréation.

### Permission denied sur les volumes

```bash
chmod 777 uploads data
```

---

## Proxy inverse (Nginx)

Pour exposer HChat derrière un reverse proxy:

```nginx
server {
    listen 80;
    server_name hchat.example.com;

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

## Production Checklist

- [ ] Générer une clé `SECRET_KEY` aléatoire forte
- [ ] Modifier `ROOM_EXPIRY_HOURS` selon vos besoins
- [ ] Configurer les logs (`LOG_LEVEL`)
- [ ] Mettre en place un reverse proxy (Nginx)
- [ ] SSL/TLS activé (pour WebSocket sécurisé: wss://)
- [ ] Backup régulier des répertoires `uploads/` et `data/`
- [ ] Limiter les extensions autorisées si nécessaire
