"""
Stockage de la configuration, partagé en mémoire entre le bot Discord
et l'API web (ils tournent dans le même processus).

Persisté dans config.json pour survivre aux redémarrages / redéploiements.
Sur Railway, pense à monter un Volume sur le dossier contenant ce fichier
si tu veux que la config survive à un redéploiement (sinon le disque est
réinitialisé à chaque déploiement).
"""

import json
import os
import threading

CONFIG_PATH = os.environ.get("CONFIG_PATH", "config.json")

DEFAULT_CONFIG = {
    "welcome": {"enabled": False, "channel": "", "message": ""},
    "leave": {"enabled": False, "channel": "", "message": ""},
    "autorole": {"enabled": False, "name": ""},
    "bank": {"enabled": False, "currency": "Crédits", "start": 100, "daily": 50, "perMsg": 1},
    "reactionRoles": {"channel": "", "pairs": []},
    "autoMessages": [],
}

_lock = threading.Lock()


def _load_from_disk():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_CONFIG)


# Config partagée en mémoire — le bot et l'API lisent/écrivent cet objet directement
config = _load_from_disk()


def save_to_disk():
    with _lock:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)


def update_config(new_values: dict):
    """Met à jour la config en mémoire et la persiste sur disque."""
    config.update(new_values)
    save_to_disk()
    return config
