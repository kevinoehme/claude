#!/usr/bin/env python3
"""briefing_trigger.py — MQTT-getriggerter Headless-Runner für den briefing-agent.

Subscribed `claude/briefing/kamen/request`. Bei jeder Nachricht startet der Listener
einmalig `claude -p` und lässt den briefing-agent das eigentliche Briefing erzeugen
(der Agent published das Ergebnis selbst nach `claude/briefing/kamen` und
`claude/briefing/kamen/text`).

Env (gleiche Konvention wie mqtt_notify.py):
    MQTT_HOST          (Pflicht)
    MQTT_PORT          (Default 1883)
    MQTT_USER          (optional)
    MQTT_PASSWORD      (optional)
    MQTT_TLS=1         (optional, TLS aktivieren)
    BRIEFING_TRIGGER_TOPIC  (Default `claude/briefing/kamen/request`)
    CLAUDE_BIN         (Default `/home/claude/.local/bin/claude`)
    CLAUDE_WORKDIR     (Default `/home/claude` — nötig damit CLAUDE.md & Agents geladen werden)
    BRIEFING_TIMEOUT   (Default 180 Sekunden)
"""
import logging
import os
import subprocess
import threading
import time

import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("briefing-trigger")

MQTT_HOST = os.environ["MQTT_HOST"]
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")
MQTT_TLS = os.environ.get("MQTT_TLS") == "1"
TRIGGER_TOPIC = os.environ.get("BRIEFING_TRIGGER_TOPIC", "claude/briefing/kamen/request")

CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "/home/claude/.local/bin/claude")
WORKDIR = os.environ.get("CLAUDE_WORKDIR", "/home/claude")
TIMEOUT = int(os.environ.get("BRIEFING_TIMEOUT", "180"))

PROMPT = (
    "Erstelle jetzt das Tagesbriefing für Kamen. "
    "Nutze den briefing-agent (Subagent) — er pusht das Ergebnis selbst per MQTT."
)

BRIEFING_COOLDOWN_SECONDS = 600

_run_lock = threading.Lock()
_last_briefing_ok = 0.0


def _run_claude():
    global _last_briefing_ok
    if time.time() - _last_briefing_ok < BRIEFING_COOLDOWN_SECONDS:
        log.info("trigger ignoriert — cooldown aktiv (letzte OK-Zeit: %.0f s ago)", time.time() - _last_briefing_ok)
        return
    if not _run_lock.acquire(blocking=False):
        log.warning("trigger ignoriert — vorheriger Lauf noch aktiv")
        return
    try:
        log.info("starte claude -p (timeout=%ds)", TIMEOUT)
        result = subprocess.run(
            [CLAUDE_BIN, "--model", "claude-haiku-4-5-20251001", "-p", PROMPT],
            cwd=WORKDIR,
            timeout=TIMEOUT,
            capture_output=True,
            text=True,
        )
        log.info(
            "claude rc=%d stdout=%dB stderr=%dB",
            result.returncode, len(result.stdout), len(result.stderr),
        )
        if result.returncode == 0:
            _last_briefing_ok = time.time()
        else:
            log.error("stderr (last 500B): %s", result.stderr[-500:])
            log.error("stdout (last 500B): %s", result.stdout[-500:])
    except subprocess.TimeoutExpired:
        log.error("claude-Lauf nach %ds abgebrochen", TIMEOUT)
    except Exception:
        log.exception("claude-Lauf fehlgeschlagen")
    finally:
        _run_lock.release()


def on_message(client, userdata, msg):
    log.info("trigger empfangen auf %s, payload=%r", msg.topic, msg.payload[:120])
    threading.Thread(target=_run_claude, daemon=True).start()


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        log.info("verbunden mit %s:%s, subscribe %s", MQTT_HOST, MQTT_PORT, TRIGGER_TOPIC)
        client.subscribe(TRIGGER_TOPIC, qos=1)
    else:
        log.error("MQTT-Connect fehlgeschlagen rc=%s", rc)


def main():
    # paho-mqtt v2.x verlangt explizit CallbackAPIVersion; auf v1.x fällt es auf alten Konstruktor zurück.
    if hasattr(mqtt, "CallbackAPIVersion"):
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="briefing-trigger")
    else:
        client = mqtt.Client(client_id="briefing-trigger")
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    if MQTT_TLS:
        client.tls_set()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_forever()


if __name__ == "__main__":
    main()
