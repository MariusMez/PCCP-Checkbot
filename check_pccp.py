#!/usr/bin/env python3
"""
PCCP Comet Watch — Observatoire R85, Antibes
=============================================
Surveille la Possible Comet Confirmation Page (PCCP) du Minor Planet Center
et alerte quand de nouveaux objets sont observables depuis l'observatoire R85.

Sources de notification disponibles :
  - Notification système macOS (osascript)
  - Message Discord (webhook)

Configuration : config.json dans le même dossier que ce script.

Auteur  : Marius Mézerette - GAPRA / Observatoire R85 — Antibes
Licence : MIT
"""

import json
import math
import urllib.request
import urllib.error
import urllib.parse
import datetime
import os
import sys
import subprocess
import platform

# ─── Fichiers ──────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
STATE_FILE  = os.path.join(SCRIPT_DIR, "state.json")
ALERT_FILE  = os.path.join(SCRIPT_DIR, "alert_pending.json")
FLAG_FILE   = os.path.join(SCRIPT_DIR, "heartbeat_alert.flag")
PCCP_URL    = "https://www.minorplanetcenter.net/iau/NEO/pccp.txt"
PCCP_PAGE   = "https://www.minorplanetcenter.net/iau/NEO/pccp_tabular.html"


# ═══════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_CONFIG = {
    # Coordonnées de l'observatoire
    "obs_lon": 7.07181,    # degrés Est  (R85 — Antibes)
    "obs_lat": 43.60,      # degrés Nord
    "obs_alt": 50,         # mètres

    # Seuils d'observabilité
    "min_alt_obj": 20.0,   # altitude min objet (degrés)
    "max_sun_alt": -12.0,  # crépuscule nautique (-18 = astronomique)
    "max_mag":     21.0,   # magnitude limite de l'instrument

    # Notifications macOS
    "macos_notify": True,
    "macos_sound":  "Glass",   # Glass, Ping, Sosumi, Basso, Hero…

    # Discord webhook
    "discord_enabled":     False,
    "discord_webhook_url": "",  # ← collez ici votre URL webhook Discord
    "discord_mention":     "",  # ex: "@here" ou "<@&123456789>" pour mentionner un rôle
}


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                user = json.load(f)
            cfg.update(user)
        except Exception as e:
            print(f"[WARN] Erreur lecture config.json : {e}", file=sys.stderr)
    return cfg


# ═══════════════════════════════════════════════════════════════════════════
# Calculs astronomiques (pure Python — aucune dépendance externe)
# ═══════════════════════════════════════════════════════════════════════════

def _r(d): return d * math.pi / 180.0
def _d(r): return r * 180.0 / math.pi


def julian_day(dt: datetime.datetime) -> float:
    """Date Julienne d'un datetime UTC naïf."""
    a = (14 - dt.month) // 12
    y = dt.year + 4800 - a
    m = dt.month + 12 * a - 3
    jdn = (dt.day + (153 * m + 2) // 5 + 365 * y
           + y // 4 - y // 100 + y // 400 - 32045)
    frac = (dt.hour - 12) / 24.0 + dt.minute / 1440.0 + dt.second / 86400.0
    return jdn + frac


def gmst_deg(jd: float) -> float:
    """Temps Sidéral Moyen de Greenwich (degrés)."""
    T = (jd - 2451545.0) / 36525.0
    return (280.46061837
            + 360.98564736629 * (jd - 2451545.0)
            + 0.000387933 * T * T
            - T ** 3 / 38710000.0) % 360.0


def altitude(ra_h: float, dec_d: float, jd: float,
             lat: float, lon: float) -> float:
    """
    Altitude d'un objet au-dessus de l'horizon local (degrés).
    ra_h  : ascension droite (heures décimales)
    dec_d : déclinaison (degrés)
    lat   : latitude observateur (degrés)
    lon   : longitude observateur (degrés Est)
    """
    lst = (gmst_deg(jd) + lon) % 360.0
    ha  = _r((lst - ra_h * 15.0) % 360.0)
    lat_r = _r(lat); dec_r = _r(dec_d)
    sin_h = (math.sin(lat_r) * math.sin(dec_r)
             + math.cos(lat_r) * math.cos(dec_r) * math.cos(ha))
    return _d(math.asin(max(-1.0, min(1.0, sin_h))))


def sun_pos(jd: float):
    """Position approx du Soleil (RA heures, Dec degrés). Précision ~1°."""
    n = jd - 2451545.0
    L = (280.460 + 0.9856474 * n) % 360.0
    g = _r((357.528 + 0.9856003 * n) % 360.0)
    lam = _r(L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    eps = _r(23.439 - 4e-7 * n)
    ra  = _d(math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))) / 15.0
    dec = _d(math.asin(math.sin(eps) * math.sin(lam)))
    return (ra % 24.0), dec


def sun_alt(jd: float, lat: float, lon: float) -> float:
    ra, dec = sun_pos(jd)
    return altitude(ra, dec, jd, lat, lon)


def observable_window(ra_h: float, dec_d: float, jd0: float,
                      lat: float, lon: float,
                      min_alt: float, max_sun: float) -> str:
    """Retourne la première fenêtre d'observabilité dans les 25h (UTC)."""
    windows, in_w, w_start = [], False, None
    for step in range(0, 25 * 60, 10):
        jd = jd0 + step / 1440.0
        ok = sun_alt(jd, lat, lon) < max_sun and altitude(ra_h, dec_d, jd, lat, lon) >= min_alt
        if ok and not in_w:
            in_w, w_start = True, jd
        elif not ok and in_w:
            in_w = False
            windows.append((w_start, jd))
        if len(windows) >= 2:
            break
    if in_w:
        windows.append((w_start, jd0 + 25 / 24.0))

    if not windows:
        return "Pas de créneau dans les 25 prochaines heures"

    def fmt(j):
        frac = (j + 0.5) % 1.0
        hh, mm = int(frac * 24), int((frac * 24 % 1) * 60)
        return f"{hh:02d}:{mm:02d} UTC"

    return " | ".join(f"{fmt(s)} → {fmt(e)}" for s, e in windows[:2])


def max_alt_24h(ra_h: float, dec_d: float, jd0: float,
                lat: float, lon: float) -> float:
    """Altitude max dans les 24h suivantes (degrés)."""
    return max(altitude(ra_h, dec_d, jd0 + s / 1440.0, lat, lon)
               for s in range(0, 24 * 60, 5))


def format_ra(ra_h: float) -> str:
    h = int(ra_h)
    m = int((ra_h - h) * 60)
    s = int(((ra_h - h) * 3600) % 60)
    return f"{h:02d}h {m:02d}m {s:02d}s"


# ═══════════════════════════════════════════════════════════════════════════
# Parsing PCCP
# ═══════════════════════════════════════════════════════════════════════════

def fetch_pccp() -> list:
    """Télécharge et parse pccp.txt du MPC."""
    try:
        req = urllib.request.Request(PCCP_URL,
                                     headers={"User-Agent": "CometWatch-R85/1.1"})
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[ERROR] Impossible de récupérer pccp.txt : {e}", file=sys.stderr)
        return []

    objects = []
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 8:
            continue
        try:
            ra_h  = float(parts[5])
            dec_d = float(parts[6])
            mag   = float(parts[7])
            disc  = f"{parts[2]}-{parts[3]}-{parts[4]}"
            i = line.find("Updated")
            updated = (line[i:].split("UT")[0].replace("Updated", "").strip() + " UT"
                       if i >= 0 else "")
            # NObs et Arc sont les 4e et 3e champs en partant de la fin
            try:
                nobs = int(parts[-4])
                arc  = float(parts[-3])
            except (ValueError, IndexError):
                nobs, arc = None, None
            objects.append(dict(desig=parts[0], score=parts[1],
                                disc=disc, ra_h=ra_h, dec_d=dec_d,
                                mag=mag, updated=updated,
                                nobs=nobs, arc=arc))
        except (ValueError, IndexError):
            continue
    return objects


# ═══════════════════════════════════════════════════════════════════════════
# État persistant
# ═══════════════════════════════════════════════════════════════════════════

def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"known": [], "last_check": None}


def save_state(s: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(s, f, indent=2)


# ═══════════════════════════════════════════════════════════════════════════
# Notifications macOS
# ═══════════════════════════════════════════════════════════════════════════

def notify_macos(title: str, body: str, subtitle: str = "", sound: str = "Glass"):
    """Envoie une notification Notification Center via osascript."""
    if platform.system() != "Darwin":
        return
    parts = [f'display notification "{body}"', f'with title "{title}"']
    if subtitle:
        parts.append(f'subtitle "{subtitle}"')
    if sound:
        parts.append(f'sound name "{sound}"')
    try:
        subprocess.run(["osascript", "-e", " ".join(parts)],
                       check=False, capture_output=True, timeout=5)
    except Exception as e:
        print(f"[WARN] Notification macOS : {e}", file=sys.stderr)


# ═══════════════════════════════════════════════════════════════════════════
# Notification Discord (webhook)
# ═══════════════════════════════════════════════════════════════════════════

def notify_discord(cfg: dict, objects_info: list, time_str: str):
    """
    Envoie un message embed Discord via webhook.
    objects_info : liste de dicts avec les clés de chaque objet + 'status', 'window'
    """
    webhook_url = cfg.get("discord_webhook_url", "").strip()
    if not webhook_url:
        print("[WARN] discord_webhook_url non défini dans config.json", file=sys.stderr)
        return

    mention = cfg.get("discord_mention", "")

    # ── Construction des embeds (un par objet) ─────────────────────────
    embeds = []
    for obj in objects_info:
        status_emoji = "🟢" if obj["obs_now"] else "🟡"
        color = 0x00FF00 if obj["obs_now"] else 0xFFAA00   # vert / orange

        fields = [
            {"name": "Score PCCP",    "value": f"{obj['score']}%",         "inline": True},
            {"name": "Magnitude",     "value": f"{obj['mag']:.1f}",         "inline": True},
            {"name": "Découverte",    "value": obj["disc"],                  "inline": True},
            {"name": "Observations",  "value": f"{obj.get('nobs', '?')} (arc {obj.get('arc', '?')} j)", "inline": True},
            {"name": "RA / Dec",
             "value": f"RA {format_ra(obj['ra_h'])}  |  Dec {obj['dec_d']:+.2f}°",
             "inline": False},
            {"name": "Altitude (maintenant)",
             "value": f"{obj['alt_now']:.1f}°  (max 24h : {obj['max_alt']:.1f}°)",
             "inline": False},
            {"name": "Fenêtre d'observation",
             "value": obj.get("window", "—"),
             "inline": False},
        ]

        embeds.append({
            "title":       f"{status_emoji} {obj['desig']} — Nouvelle comète possible PCCP",
            "description": (f"**Observable maintenant** depuis R85 !" if obj["obs_now"]
                            else f"Observable ce soir depuis R85"),
            "color":       color,
            "fields":      fields,
            "footer":      {"text": f"PCCP Watch R85 — Antibes | {time_str}"},
            "url":         PCCP_PAGE,
        })

    # Discord limite à 10 embeds par message
    for i in range(0, len(embeds), 10):
        payload = {"embeds": embeds[i:i+10]}
        if mention and i == 0:
            payload["content"] = mention
        data = json.dumps(payload).encode("utf-8")
        try:
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers={"Content-Type": "application/json",
                         "User-Agent": "CometWatch-R85/1.1"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                status = r.status
                if status not in (200, 204):
                    print(f"[WARN] Discord webhook réponse inattendue : {status}",
                          file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] Discord webhook : {e}", file=sys.stderr)


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main():
    cfg = load_config()

    lat     = cfg["obs_lat"]
    lon     = cfg["obs_lon"]
    min_alt = cfg["min_alt_obj"]
    max_sun = cfg["max_sun_alt"]
    max_mag = cfg["max_mag"]

    now      = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    jd_now   = julian_day(now)
    s_alt    = sun_alt(jd_now, lat, lon)
    is_night = s_alt < max_sun
    time_str = now.strftime("%Y-%m-%d %H:%M UTC")

    night_label = ("nuit astronomique" if s_alt < -18
                   else "nuit nautique" if is_night
                   else "crépuscule/jour")

    # ── Récupération PCCP ───────────────────────────────────────────────
    objects = fetch_pccp()
    if not objects:
        print(f"[{time_str}] Aucun objet récupéré (erreur réseau ?).")
        return

    # ── Détection nouveaux objets ────────────────────────────────────────
    state      = load_state()
    known      = set(state.get("known", []))
    current    = {o["desig"] for o in objects}
    new_desigs = current - known
    first_run  = len(known) == 0

    state["known"] = list(current)
    state["last_check"] = time_str
    save_state(state)

    # ── Rapport texte ────────────────────────────────────────────────────
    lines = [
        f"🔭 PCCP Comet Watch R85 | {time_str}",
        f"☀️  Soleil : {s_alt:.1f}° ({night_label})",
        f"📋 Total PCCP : {len(objects)} objet(s) | 🆕 Nouveaux : {len(new_desigs)}",
        "",
    ]

    alert_objects  = []   # désignations à notifier
    discord_embeds = []   # données pour Discord

    if new_desigs:
        lines += ["═" * 50, "🆕 NOUVEAUX OBJETS SUR LA PCCP", "═" * 50]

        for obj in objects:
            if obj["desig"] not in new_desigs:
                continue

            ra_h, dec_d, mag = obj["ra_h"], obj["dec_d"], obj["mag"]
            alt_now = altitude(ra_h, dec_d, jd_now, lat, lon)
            mx_alt  = max_alt_24h(ra_h, dec_d, jd_now, lat, lon)

            obs_now     = is_night and alt_now >= min_alt and mag <= max_mag
            obs_tonight = mx_alt >= min_alt and mag <= max_mag

            lines += [
                f"\n• Désignation : {obj['desig']}",
                f"  Score PCCP   : {obj['score']}%",
                f"  Découverte   : {obj['disc']}",
                f"  Mise à jour  : {obj['updated']}",
                f"  Position     : RA {format_ra(ra_h)}  Dec {dec_d:+.2f}°",
                f"  Magnitude    : {mag:.1f}",
                f"  Observations : {obj.get('nobs', '?')}  (arc : {obj.get('arc', '?')} j)",
                f"  Altitude now : {alt_now:.1f}°  (max 24h : {mx_alt:.1f}°)",
            ]

            window = ""
            if obs_now:
                lines.append("  🟢 OBSERVABLE MAINTENANT depuis R85 !")
                window = "Actuellement observable"
                alert_objects.append(obj["desig"])
                discord_embeds.append({**obj, "alt_now": alt_now, "max_alt": mx_alt,
                                       "obs_now": True, "window": window})
            elif obs_tonight:
                window = observable_window(ra_h, dec_d, jd_now, lat, lon, min_alt, max_sun)
                lines.append(f"  🟡 Observable ce soir → {window}")
                alert_objects.append(obj["desig"])
                discord_embeds.append({**obj, "alt_now": alt_now, "max_alt": mx_alt,
                                       "obs_now": False, "window": window})
            else:
                reasons = []
                if mag > max_mag:
                    reasons.append(f"trop faible (mag {mag:.1f} > limite {max_mag})")
                if mx_alt < min_alt:
                    reasons.append(f"jamais > {min_alt}° (max {mx_alt:.1f}°)")
                lines.append(f"  🔴 Non observable : {', '.join(reasons)}")
                # ← pas d'ajout à discord_embeds : objet ignoré dans Discord

        lines += ["", f"🔗 {PCCP_PAGE}"]

    elif first_run:
        lines.append("📋 Liste initiale (premier lancement) :")
        for obj in objects:
            a   = altitude(obj["ra_h"], obj["dec_d"], jd_now, lat, lon)
            mx  = max_alt_24h(obj["ra_h"], obj["dec_d"], jd_now, lat, lon)
            ico = ("🟢" if (is_night and a >= min_alt and obj["mag"] <= max_mag)
                   else "🟡" if (mx >= min_alt and obj["mag"] <= max_mag) else "🔴")
            nobs_str = f"  nobs={obj.get('nobs', '?')}" if obj.get('nobs') is not None else ""
            lines.append(f"  {ico} {obj['desig']}  mag={obj['mag']:.1f}  alt={a:.1f}°{nobs_str}")
        lines.append("\n✅ État initial enregistré. Surveillance active toutes les heures.")
    else:
        lines.append("✓ Aucun nouvel objet depuis la dernière vérification.")

    report = "\n".join(lines)
    print(report)

    # ── Notifications ────────────────────────────────────────────────────
    if alert_objects:
        # Fichier d'alerte (heartbeat OpenClaw)
        with open(ALERT_FILE, "w") as f:
            json.dump({"time": time_str, "objects": alert_objects, "report": report}, f, indent=2)
        open(FLAG_FILE, "w").close()

        count    = len(alert_objects)
        plural_e = "s" if count > 1 else ""
        obs_list = ", ".join(alert_objects)

        # macOS
        if cfg.get("macos_notify", True):
            notify_macos(
                title    = f"🔭 Nouvelle{plural_e} comète{plural_e} PCCP — R85",
                subtitle = f"{count} objet{plural_e} observable{plural_e} depuis Antibes",
                body     = obs_list,
                sound    = cfg.get("macos_sound", "Glass"),
            )

        # Discord — discord_embeds ne contient déjà que les objets observables
        if cfg.get("discord_enabled", False):
            notify_discord(cfg, discord_embeds, time_str)


if __name__ == "__main__":
    main()
