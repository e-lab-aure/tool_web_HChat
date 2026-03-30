"""
Liste de mots francais courants pour la generation d'identifiants de room memorables.
Criteres de selection : mots du quotidien, sans accents, 2 a 8 caracteres.
Format de room : mot1-mot2-mot3-mot4 (ex: chat-nuage-pain-soleil)
"""

WORDS: list[str] = [
    # Nature - ciel et meteo
    "soleil", "lune", "etoile", "nuage", "pluie", "neige", "vent", "brume",
    "orage", "eclair", "arc", "aube", "aurore", "nuit", "matin",
    "midi", "soir", "givre", "gel", "verglas", "grele", "rosee",
    "brise", "rafale", "tempete", "cyclone",

    # Nature - terre et eau
    "mer", "ocean", "lac", "fleuve", "riviere", "source", "torrent", "cascade",
    "marais", "etang", "crique", "baie", "cap", "ile", "delta",
    "plage", "dune", "falaise", "roche", "pierre", "sable", "argile",
    "montagne", "colline", "vallee", "plateau", "desert", "foret", "jungle",
    "savane", "prairie", "champ", "bocage", "verger", "toundra",
    "glacier", "iceberg", "volcan", "cratere", "grotte", "caverne", "gouffre",

    # Nature - plantes
    "arbre", "fleur", "herbe", "feuille", "racine", "graine", "bourgeon",
    "ecorce", "branche", "tronc", "tige", "fougere", "mousse", "lierre",
    "ortie", "rosier", "tulipe", "iris", "lilas", "jasmin", "lavande",
    "mimosa", "sapin", "chene", "bouleau", "peuplier", "saule", "hetre",
    "erable", "noyer", "olivier", "citron", "bambou", "cactus", "lotus",
    "pivoine", "dahlia",

    # Nature - animaux
    "chat", "chien", "cheval", "vache", "mouton", "lapin", "cochon", "chevre",
    "canard", "poule", "oie", "dinde", "pigeon", "hibou", "aigle", "faucon",
    "cigogne", "perroquet", "pingouin", "dauphin", "baleine", "requin", "truite",
    "saumon", "carpe", "coquille", "crabe", "homard", "crevette", "pieuvre",
    "lion", "tigre", "ours", "loup", "renard", "cerf", "sanglier",
    "lynx", "jaguar", "leopard", "guepard", "girafe", "zebre", "elephant",
    "chameau", "gazelle", "gorille",
    "singe", "koala", "panda", "castor", "loutre", "belette",
    "herisson", "taupe", "souris", "ecureuil", "lezard", "gecko", "serpent",
    "tortue", "grenouille", "crapaud", "papillon", "abeille",
    "frelon", "libellule", "coccinelle", "fourmi", "scarabee",

    # Couleurs
    "rouge", "bleu", "vert", "jaune", "orange", "violet", "rose", "blanc",
    "noir", "gris", "brun", "beige", "cyan", "magenta", "indigo", "turquoise",
    "or", "argent", "bronze", "ivoire", "ecru", "ocre", "carmin", "azur",
    "marine", "olive", "corail", "cerise", "lilas", "ambre", "jade", "opale",

    # Aliments et boissons
    "pain", "lait", "oeuf", "beurre", "fromage", "yaourt", "miel", "sucre",
    "sel", "poivre", "farine", "riz", "pate", "soupe", "salade", "tomate",
    "carotte", "oignon", "ail", "persil", "menthe", "basilic", "thym",
    "pomme", "poire", "cerise", "fraise", "framboise", "myrtille", "citron",
    "orange", "abricot", "peche", "prune", "figue", "datte", "noix", "noisette",
    "amande", "pistache", "cafe", "the", "jus", "sirop", "eau", "biere",
    "vin", "cidre", "limonade", "sorbet", "glace", "gateau", "tarte", "brioche",
    "croissant", "muffin", "biscuit", "chocolat", "caramel", "vanille", "cannelle",

    # Maison et objets du quotidien
    "maison", "villa", "chateau", "chalet", "cabane", "tente", "porte",
    "fenetre", "mur", "toit", "plafond", "plancher", "escalier", "couloir",
    "salon", "cuisine", "chambre", "bureau", "grenier", "cave", "garage",
    "jardin", "balcon", "terrasse", "piscine", "table", "chaise", "fauteuil",
    "canape", "lit", "armoire", "tiroir", "etagere", "miroir", "lampe",
    "lustre", "rideau", "tapis", "coussin", "couette", "oreiller", "horloge",
    "reveil", "vase", "bougie", "tableau", "cadre", "livre", "journal",
    "crayon", "stylo", "gomme", "regle", "ciseaux", "colle", "agraffe",
    "envelop", "boite", "valise", "sac", "panier", "filet", "corbeille",
    "verre", "tasse", "bol", "assiette", "couteau", "fourchette", "cuiller",
    "casserole", "poele", "four", "frigo", "robot", "mixeur", "moulin",

    # Vetements et accessoires
    "robe", "jupe", "pantalon", "jean", "short", "veste", "manteau",
    "chemise", "pull", "gilet", "parka", "cape", "poncho",
    "botte", "sandale", "talon",
    "chapeau", "bonnet", "echarpe", "gant", "ceinture",
    "cravate", "noeud", "collier", "bracelet", "bague", "boucle", "montre",
    "lunette", "sac", "pochette",

    # Transports et deplacement
    "voiture", "moto", "velo", "scooter", "bus", "metro", "train", "tram",
    "avion", "bateau", "ferry", "yacht", "canoe", "kayak", "planche",
    "fusee", "satellite",
    "pont", "tunnel", "route", "chemin", "sentier", "piste", "avenue",
    "ruelle", "passage",

    # Professions et activites
    "pilote", "docteur", "chef", "boulanger", "peintre",
    "musicien", "acteur", "danseur", "nageur", "coureur",
    "grimpeur", "plongeur", "archer", "cavalier",

    # Loisirs et sports
    "musique", "guitare", "piano", "violon", "flute", "tambour", "trompette",
    "cinema", "theatre", "livre", "roman", "poeme", "dessin", "peinture",
    "photo", "video", "jeu", "puzzle", "echecs", "dames", "cartes",
    "football", "tennis", "rugby", "basket", "volley", "natation", "gym",
    "yoga", "boxe", "judo", "karate", "surf", "ski", "patin",
    "escalade", "camping", "peche", "chasse",

    # Corps humain (inoffensifs)
    "main", "bras", "jambe", "pied", "tete", "dos", "coeur", "cerveau",
    "oeil", "oreille", "nez", "bouche", "dent", "langue", "cheveux",
    "sourcil", "epaule", "poignet", "coude", "genou", "cheville", "ongle",

    # Sentiments et qualites
    "joie", "calme", "paix", "amour", "espoir", "courage", "confiance",
    "honneur", "sagesse", "grace", "beaute", "force", "douceur", "ardeur",
    "charme", "talent", "energie", "vigueur", "patience", "bonheur",
    "lumiere", "eclat", "harmonie",

    # Adjectifs et mots descriptifs
    "grand", "petit", "long", "court", "large", "etroit", "haut", "bas",
    "lourd", "leger", "rapide", "lent", "doux", "dur", "chaud", "froid",
    "frais", "tiede", "clair", "sombre", "vif", "terne", "lisse", "rugueux",
    "plat", "courbe", "rond", "carre", "pointu", "creux", "plein", "vide",
    "neuf", "vieux", "jeune", "ancien", "moderne", "simple", "complexe",
    "serein", "joyeux", "fier", "sage", "brave", "libre", "unique",
    "solide", "fragile", "dense", "rare", "commun", "noble", "humble",

    # Divers memorables
    "atlas", "boussole", "carte", "globe", "horizon", "zenith",
    "tropique", "pole", "archipel", "canyon",
    "bassin", "sommet", "versant", "barriere",
    "fontaine", "puits", "citerne", "canal", "digue", "ecluse",
    "phare", "balise", "signal", "repere", "borne",
    "cristal", "diamant", "rubis", "saphir", "topaze", "agate",
    "granit", "marbre", "basalte", "silex", "quartz",
    "comete", "galaxie", "pulsar", "quasar", "plasma",
    "aurore", "equinoxe", "solstice",
]

# Deduplique et filtre : uniquement ASCII, 2-8 caracteres
WORDS = sorted({
    w for w in WORDS
    if 2 <= len(w) <= 8 and w.isalpha() and w.isascii()
})
