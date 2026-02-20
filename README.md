# 🔭 PCCP Comet Watch — Observatoire R85 (Antibes)

Surveille la page [PCCP du MPC](https://www.minorplanetcenter.net/iau/NEO/pccp_tabular.html)
toutes les heures et vous alerte si de nouveaux objets sont observables depuis **R85**.

---

## Installation sur macOS

### 1. Copier les fichiers

Placez ce dossier où vous voulez, par exemple :
```
~/comet-watch/
```

### 2. Rendre le wrapper exécutable

```bash
chmod +x ~/comet-watch/cron_wrapper.sh
```

### 3. Autoriser les notifications Python/Terminal

> **Important** : pour que les notifications macOS fonctionnent depuis un script,
> il faut que `Terminal.app` (ou votre terminal) ait la permission d'envoyer des notifications.
>
> Allez dans : **Réglages Système → Notifications → Terminal** → activez « Autoriser les notifications »

### 4. Planification horaire (crontab)

```bash
crontab -e
```

Ajoutez la ligne suivante (remplacez le chemin par le vôtre) :

```
0 * * * * /bin/bash /Users/VOTRE_NOM/comet-watch/cron_wrapper.sh
```

Vérifiez avec `crontab -l`.

> Voir la [documentation complète](DOCUMENTATION.md#6-planification-automatique)
> pour plus de détails et l'alternative LaunchAgent.

---

## Test manuel

```bash
python3 ~/comet-watch/check_pccp.py
```

---

## Paramètres (en tête de `check_pccp.py`)

| Variable | Valeur | Description |
|----------|--------|-------------|
| `MAX_MAG` | `21.0` | Magnitude limite de votre instrument |
| `MIN_ALT_OBJ` | `20.0°` | Altitude minimale objet (évite l'atmosphère) |
| `MAX_SUN_ALT` | `-12.0°` | Seuil nuit (crépuscule nautique) |
| `OBS_LAT` | `43.60°N` | Latitude R85 |
| `OBS_LON` | `7.07181°E` | Longitude R85 |

---

## Fichiers générés

| Fichier | Rôle |
|---------|------|
| `state.json` | Liste des objets déjà connus |
| `watch.log` | Journal des vérifications |
| `alert_pending.json` | Alerte en attente (supprimée après notification) |
| `heartbeat_alert.flag` | Flag pour OpenClaw heartbeat |
