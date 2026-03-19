# tool_web_HChat

Chat en temps réel avec partage de fichiers, basé sur WebSocket. Application Python autonome sans framework frontend.

## Lancement

```bash
pip install -r requirements.txt
python server.py
# → http://localhost:5000
```

## Schéma des interactions

```
┌─────────────────────────────────────────────────────────────┐
│                        Navigateur                           │
│                                                             │
│   ┌─────────────┐        ┌──────────────────────────────┐  │
│   │  Zone chat  │        │        Zone fichiers         │  │
│   │             │        │  [Upload form]  [Liste /files]│  │
│   └─────────────┘        └──────────────────────────────┘  │
│          │                        │             ↑           │
│      WS send                 POST /upload   GET /files      │
│     (JSON+HTML)              (multipart)   (polling 3s)     │
└──────────│────────────────────────│─────────────│───────────┘
           │                        │             │
           ▼                        ▼             │
┌─────────────────────────────────────────────────────────────┐
│                      server.py (aiohttp)                    │
│                                                             │
│   GET /          → Sert le HTML embarqué (INDEX_HTML)       │
│   GET /ws        → WebSocket handler                        │
│   POST /upload   → Sauvegarde dans uploads/                 │
│   GET /files     → Liste les fichiers (JSON)                │
│   GET /uploads/  → Téléchargement d'un fichier              │
│                                                             │
│   ws_clients = { ws1, ws2, ws3, ... }  ← set en mémoire    │
│                                                             │
│   À chaque message reçu sur /ws :                          │
│   ┌─────────────────────────────────────────────────────┐  │
│   │  Client A ──→ serveur ──→ broadcast ──→ tous (A+B+C)│  │
│   └─────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
                    ┌──────────────────┐
                    │   uploads/       │
                    │  fichier1.pdf    │
                    │  fichier2.zip    │
                    │  ...             │
                    └──────────────────┘
```

## Fonctionnement du chat

- Chaque client reçoit un UUID généré côté navigateur (stocké dans `localStorage`)
- Les messages sont envoyés en JSON `{ message: HTML, plain: texte, userId: UUID }`
- Le serveur ajoute l'horodatage et broadcast à tous les clients connectés
- Le client distingue ses propres messages (`mine` en bleu) des autres (`other` en gris)

## Formatage

| Action | Comportement |
|--------|-------------|
| Coller avec formatage activé | Conserve gras, italique, code, tableaux, listes |
| Coller avec formatage désactivé | Texte brut uniquement |
| `Entrée` | Envoyer le message |
| `Shift+Entrée` | Saut de ligne |
| 📋 | Copie le message (HTML riche ou texte brut selon le mode) |
