# 🔭 PCCP Comet Watch — Documentation complète
### Observatoire R85 · Telescope Léonard de Vinci, GAPRA, Antibes

---

## Table des matières

1. [Présentation](#1-présentation)
2. [Architecture](#2-architecture)
3. [Installation sur macOS](#3-installation-sur-macos)
4. [Configuration (`config.json`)](#4-configuration-configjson)
5. [Notifications Discord](#5-notifications-discord)
6. [Planification automatique (LaunchAgent)](#6-planification-automatique-launchagent)
7. [Calculs astronomiques](#7-calculs-astronomiques)
8. [Utilisation en ligne de commande](#8-utilisation-en-ligne-de-commande)
9. [Fichiers générés](#9-fichiers-générés)
10. [Dépannage](#10-dépannage)
11. [Feuille de route](#11-feuille-de-route)

---

## 1. Présentation

**PCCP Comet Watch** est un script Python autonome (zéro dépendance externe) qui :

- Télécharge toutes les heures le fichier `pccp.txt` depuis le
  [Minor Planet Center (MPC)](https://www.minorplanetcenter.net/iau/NEO/pccp_tabular.html)
- Détecte les **nouveaux objets** apparus depuis la dernière vérification
- Calcule si ces objets sont **observables depuis votre observatoire** (R85 — Antibes)
  en tenant compte de l'heure, de la position du Soleil et de l'altitude de l'objet
- Envoie des **alertes** via :
  - Notification système **macOS** (Centre de notifications)
  - Message **Discord** (webhook, avec embed riche)

### Qu'est-ce que la PCCP ?

La *Possible Comet Confirmation Page* liste des objets à orbites cométaires dont la
nature n'a pas encore été confirmée. Les observateurs sont invités à les imager pour
confirmer (ou infirmer) une activité cométaire (chevelure, queue).

> ⚠️ Règle MPC : ne signalez une activité cométaire **que** si vous la détectez
> clairement. Un faux rapport peut nuire à la réputation de votre station.

---

## 2. Architecture

```
comet-watch/
├── check_pccp.py              ← Script principal
├── config.json                ← Configuration (à éditer)
├── cron_wrapper.sh            ← Lanceur shell (appelé par LaunchAgent/cron)
├── fr.gapra.r85.cometwatch.plist  ← LaunchAgent macOS
├── state.json                 ← État : liste des objets déjà connus [auto-généré]
├── watch.log                  ← Journal des vérifications [auto-généré]
├── alert_pending.json         ← Alerte en attente [auto-généré, supprimé après]
├── heartbeat_alert.flag       ← Flag pour OpenClaw heartbeat [auto-généré]
├── DOCUMENTATION.md           ← Ce fichier
└── README.md                  ← Guide de démarrage rapide
```

**Flux d'exécution :**

```
LaunchAgent (toutes les heures)
  └─► cron_wrapper.sh
        └─► check_pccp.py
              ├── Télécharge pccp.txt
              ├── Compare avec state.json
              ├── Calcule l'observabilité
              ├── Notification macOS  ──► Centre de notifications
              └── Notification Discord ─► Webhook → groupe Discord
```

---

## 3. Installation sur macOS

### Prérequis

- macOS 12 (Monterey) ou supérieur recommandé
- Python 3.9+ (inclus sur macOS ou via `brew install python`)
- Connexion internet

### Étapes

**1. Copier le dossier**

```bash
cp -r comet-watch/ ~/comet-watch/
cd ~/comet-watch/
```

**2. Rendre le wrapper exécutable**

```bash
chmod +x ~/comet-watch/cron_wrapper.sh
```

**3. Autoriser les notifications (important !)**

Pour que les notifications fonctionnent depuis un script en arrière-plan :

> **Réglages Système → Notifications → Terminal**
> → Activez *"Autoriser les notifications"*
> → Style : Alertes (pour qu'elles restent à l'écran)

**4. Tester manuellement**

```bash
# Premier lancement : affiche les objets actuels et enregistre l'état initial
python3 ~/comet-watch/check_pccp.py
```

Si tout fonctionne, vous verrez le rapport dans le terminal et (si des objets
sont observables) une notification macOS.

**5. Installer la planification horaire**

Voir [section 6](#6-planification-automatique-launchagent).

---

## 4. Configuration (`config.json`)

Éditez `config.json` pour adapter le script à votre setup.

```json
{
  "obs_lon":    7.07181,    // Longitude observatoire (degrés Est)
  "obs_lat":    43.60,      // Latitude (degrés Nord)
  "obs_alt":    50,         // Altitude (mètres)

  "min_alt_obj": 20.0,      // Altitude minimale objet pour observation (°)
  "max_sun_alt": -12.0,     // Seuil nuit : -12 nautique, -18 astronomique
  "max_mag":     21.0,      // Magnitude limite de votre instrument

  "macos_notify": true,     // Activer les notifications macOS
  "macos_sound":  "Glass",  // Son : Glass, Ping, Sosumi, Basso, Hero, Frog…

  "discord_enabled":     false,   // true pour activer Discord
  "discord_webhook_url": "",      // URL du webhook Discord (voir section 5)
  "discord_mention":     ""       // "@here" ou "<@&ROLE_ID>" ou "" pour aucune mention
}
```

### Recommandations selon l'instrument

| Instrument                   | `max_mag` conseillée |
|------------------------------|----------------------|
| Lunette 80 mm                | 13.0                 |
| Newton 200 mm (visuel)       | 15.0                 |
| Newton 200 mm + caméra CCD   | 18.0–19.0            |
| Schmidt-Cassegrain 300 mm+   | 20.0–21.0            |
| Télescope professionnel      | 22.0+                |

La PCCP liste généralement des objets entre magnitude **18 et 22**.

---

## 5. Notifications Discord

### Créer un webhook Discord

1. Ouvrez votre **serveur Discord**
2. Faites un clic droit sur le **canal** où vous voulez les alertes
3. **Modifier le canal → Intégrations → Webhooks → Nouveau webhook**
4. Donnez-lui un nom (ex : `🔭 PCCP Watch`) et une icône si souhaité
5. Cliquez **Copier l'URL du webhook**

L'URL ressemble à :
```
https://discord.com/api/webhooks/123456789012345678/xxxxxxxxxxxxxxxxxxxx
```

### Configurer le script

Dans `config.json` :

```json
{
  "discord_enabled":     true,
  "discord_webhook_url": "https://discord.com/api/webhooks/VOTRE_ID/VOTRE_TOKEN",
  "discord_mention":     "@here"
}
```

**Options pour `discord_mention` :**
- `""` — aucune mention, message silencieux
- `"@here"` — mentionne les membres actifs du canal
- `"@everyone"` — mentionne tout le monde (déconseillé)
- `"<@&123456789>"` — mentionne un rôle spécifique (remplacez par l'ID du rôle)

### Format du message Discord

Chaque nouvel objet observable génère un **embed** Discord avec :

- 🟢 Vert si observable **maintenant**
- 🟡 Orange si observable **ce soir**
- Champs : score PCCP, magnitude, RA/Dec, altitude, fenêtre d'observation
- Lien direct vers la page PCCP du MPC

---

## 6. Planification automatique

### Méthode recommandée : crontab

La crontab est la méthode la plus simple et la plus fiable sur macOS.

**1. Ouvrir l'éditeur crontab**

```bash
crontab -e
```

**2. Ajouter la ligne suivante** (exécution toutes les heures, à la minute 0) :

```
0 * * * * /bin/bash /Users/VOTRE_NOM/comet-watch/cron_wrapper.sh
```

Remplacez `/Users/VOTRE_NOM/comet-watch/` par le chemin réel vers votre dossier.

**3. Vérifier**

```bash
crontab -l
# Doit afficher la ligne ajoutée
```

> **Note macOS** : au premier déclenchement, macOS peut afficher une popup demandant
> d'autoriser `cron` dans **Réglages Système → Confidentialité et sécurité → Accès
> complet au disque**. Acceptez pour que le script fonctionne correctement.

### Commandes utiles

```bash
# Voir la crontab actuelle
crontab -l

# Éditer la crontab
crontab -e

# Voir les logs du script
tail -f ~/comet-watch/watch.log
```

### Fréquence

Le script tourne toutes les heures. La PCCP du MPC est mise à jour plusieurs fois
par jour.

### Alternative : LaunchAgent

Le LaunchAgent macOS (`launchd`) est une alternative qui se relance au démarrage
du Mac et ne dépend pas d'une session ouverte.

> **Attention** : si votre dossier de projet est synchronisé via Google Drive ou
> iCloud Drive, le LaunchAgent risque de ne pas fonctionner. macOS marque ces fichiers
> avec l'attribut `com.apple.provenance` qui empêche `launchd` de les exécuter
> (erreur "Operation not permitted"). Utilisez la crontab dans ce cas.

**Installation du LaunchAgent** :

1. Éditez `fr.gapra.r85.cometwatch.plist` et remplacez le chemin vers
   `cron_wrapper.sh` par votre chemin réel
2. Copiez et chargez :

```bash
cp ~/comet-watch/fr.gapra.r85.cometwatch.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/fr.gapra.r85.cometwatch.plist
```

3. Vérifiez : `launchctl list | grep cometwatch`

---

## 7. Calculs astronomiques

Le script n'utilise **aucune bibliothèque externe**. Tous les calculs sont implémentés
en Python pur avec des formules standards.

### Temps Sidéral de Greenwich (GMST)

```
GMST = 280.46061837 + 360.98564736629 × (JD − 2451545.0) + corrections T²/T³
```

Le Temps Sidéral Local (LST) = GMST + longitude observatoire.

### Angle horaire et altitude

```
H = LST − α  (α = ascension droite en degrés)

sin(alt) = sin(φ)·sin(δ) + cos(φ)·cos(δ)·cos(H)
```

où φ = latitude de l'observatoire, δ = déclinaison de l'objet.

### Position du Soleil

Formule de faible précision (~1°) suffisante pour déterminer nuit/jour :

```
λ = L + 1.915·sin(g) + 0.020·sin(2g)
```

où L = longitude écliptique moyenne, g = anomalie moyenne.

### Fenêtre d'observation

L'algorithme scrute les 25 prochaines heures par pas de 10 minutes et identifie
les plages où simultanément :
- Altitude du Soleil < `max_sun_alt` (nuit)
- Altitude de l'objet ≥ `min_alt_obj`
- Magnitude ≤ `max_mag`

### Précision

| Calcul              | Précision      |
|---------------------|----------------|
| Position du Soleil  | ~1°            |
| Altitude objet      | ~0.1°          |
| Fenêtre d'obs.      | ~10 min        |
| GMST                | < 0.01°        |

Cette précision est largement suffisante pour la planification d'observations.

---

## 8. Utilisation en ligne de commande

```bash
# Vérification manuelle
python3 ~/comet-watch/check_pccp.py

# Réinitialiser l'état (simule un premier lancement — tous les objets seront "nouveaux")
rm ~/comet-watch/state.json && python3 ~/comet-watch/check_pccp.py

# Voir le journal
tail -50 ~/comet-watch/watch.log

# Voir l'alerte en attente (si elle existe)
cat ~/comet-watch/alert_pending.json

# Tester le wrapper complet
bash ~/comet-watch/cron_wrapper.sh
```

---

## 9. Fichiers générés

| Fichier               | Description                                            | Sûr à supprimer ? |
|-----------------------|--------------------------------------------------------|-------------------|
| `state.json`          | Désignations des objets déjà connus                    | Oui (repart à zéro) |
| `watch.log`           | Journal horodaté de chaque vérification                | Oui               |
| `alert_pending.json`  | Rapport de la dernière alerte non encore acquittée     | Oui               |
| `heartbeat_alert.flag`| Flag pour OpenClaw heartbeat                           | Oui               |

---

## 10. Dépannage

### "Aucun objet récupéré (erreur réseau)"

- Vérifiez votre connexion internet
- Testez : `curl https://www.minorplanetcenter.net/iau/NEO/pccp.txt`
- Le MPC peut être temporairement indisponible — le script réessaiera à la prochaine heure

### Les notifications macOS n'apparaissent pas

1. **Réglages Système → Notifications → Terminal** → vérifiez que c'est activé
2. Le mode "Ne pas déranger" (Focus) peut bloquer les notifications
3. Testez manuellement :
   ```bash
   osascript -e 'display notification "Test" with title "PCCP Watch" sound name "Glass"'
   ```
4. Si vous utilisez un terminal autre que Terminal.app (iTerm2, etc.), autorisez-le aussi

### Le webhook Discord renvoie une erreur

- Vérifiez que l'URL webhook est complète et correcte dans `config.json`
- Assurez-vous que `discord_enabled` est `true`
- Vérifiez que le bot/webhook a les permissions pour poster dans le canal
- Consultez `/tmp/cometwatch.stderr.log` pour les détails de l'erreur

### "Operation not permitted" avec le LaunchAgent

Si `/tmp/cometwatch.stderr.log` contient `Operation not permitted`, c'est
probablement dû à l'attribut `com.apple.provenance` de macOS. Ce marqueur est
appliqué automatiquement aux fichiers synchronisés via **Google Drive** ou
**iCloud Drive** et empêche `launchd` de les exécuter.

**Solution** : utilisez la **crontab** à la place (voir [section 6](#6-planification-automatique)).

### Le LaunchAgent ne démarre pas

```bash
# Vérifier la syntaxe du plist
plutil -lint ~/Library/LaunchAgents/fr.gapra.r85.cometwatch.plist

# Vérifier les logs système
log show --predicate 'process == "launchd"' --last 1h | grep cometwatch
```

### Tous les objets sont marqués "non observables"

- Vérifiez `max_mag` dans `config.json` — la PCCP liste surtout des objets > mag 18
- Vérifiez que l'heure système est correcte (les calculs dépendent de l'heure UTC)
- Supprimez `state.json` et relancez pour voir tous les objets actuels

---

## 11. Feuille de route

Améliorations possibles :

- [ ] Calcul de l'élongation lunaire (éviter la Pleine Lune)
- [ ] Génération d'une carte céleste (position sur fond d'étoiles)
- [ ] Notification par email (SMTP)
- [ ] Interface web légère (Flask/FastAPI) pour consulter le statut
- [ ] Ephémérides MPC directes via l'API (coordonnées précises au lieu de RA/Dec bruts)
- [ ] Filtre par constellation ou région du ciel
- [ ] Support Windows (notification via `win10toast`)

---

*PCCP Comet Watch v1.1 — GAPRA / Observatoire R85, Antibes*
*Données : [Minor Planet Center](https://www.minorplanetcenter.net) — IAU*
