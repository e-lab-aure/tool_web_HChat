FROM python:3.11-slim

WORKDIR /app

# Installer les dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copier les requirements et installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier l'application
COPY . .

# Créer les répertoires pour les uploads et données
RUN mkdir -p uploads data

# Exposer le port (8080 par défaut)
EXPOSE 8080

# Variables d'environnement par défaut
ENV PORT=8080 \
    HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/ || exit 1

# Lancer l'application
CMD ["python", "server.py"]
