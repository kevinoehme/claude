"""MQTT-Notification-MCP für Briefing-/Alert-Workflows.

Generischer Notification-Channel: jedes Tool-/Agent-System kann via
`send_notification` eine Nachricht auf einen MQTT-Topic schicken. Home
Assistant abonniert die Topics und routet z.B. Briefings an einen
Alexa-Echo-Dot oder triggert andere Automationen.

Konfiguration via Env-Vars:
- MQTT_HOST           (Pflicht)
- MQTT_PORT           (Default 1883)
- MQTT_USER           (optional)
- MQTT_PASSWORD       (optional)
- MQTT_DEFAULT_TOPIC  (optional, Default "claude/notifications")
- MQTT_TLS            (optional, "1"/"true" → TLS auf Default-Port 8883)
"""

import json
import os
import ssl

import paho.mqtt.publish as publish

from mcp.server.fastmcp import FastMCP

from profiling import module_load, profile

mcp = FastMCP("mqtt_notify")
module_load("mqtt_notify")

MQTT_HOST = os.environ["MQTT_HOST"]
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")
DEFAULT_TOPIC = os.environ.get("MQTT_DEFAULT_TOPIC", "claude/notifications")
USE_TLS = os.environ.get("MQTT_TLS", "").lower() in ("1", "true", "yes")


def _auth():
    if MQTT_USER:
        return {"username": MQTT_USER, "password": MQTT_PASSWORD or ""}
    return None


def _tls():
    if USE_TLS:
        return {"tls_version": ssl.PROTOCOL_TLS_CLIENT}
    return None


@mcp.tool()
@profile("mqtt_notify.send_notification")
def send_notification(
    message: str,
    topic: str | None = None,
    title: str | None = None,
    retain: bool = False,
    qos: int = 0,
) -> str:
    """Sendet eine Nachricht auf einen MQTT-Topic.

    - `message`: Nachrichtentext (Pflicht).
    - `topic`: MQTT-Topic. Default = MQTT_DEFAULT_TOPIC ("claude/notifications").
    - `title`: Optionaler Titel — wird zusammen mit `message` als JSON-Objekt
      `{"title": ..., "message": ...}` gesendet. Ohne `title` wird der
      Plain-Text-`message` gesendet.
    - `retain`: True → Broker behält den letzten Wert für neue Subscriber.
    - `qos`: 0/1/2 (Default 0).
    """
    target_topic = topic or DEFAULT_TOPIC
    if title:
        payload = json.dumps({"title": title, "message": message}, ensure_ascii=False)
    else:
        payload = message

    publish.single(
        topic=target_topic,
        payload=payload,
        qos=qos,
        retain=retain,
        hostname=MQTT_HOST,
        port=MQTT_PORT,
        auth=_auth(),
        tls=_tls(),
        client_id="claude-mqtt-notify",
        keepalive=10,
    )
    return f"📌 Nachricht gesendet → {target_topic} ({len(payload)} Bytes)"


@mcp.tool()
@profile("mqtt_notify.send_notifications_multi")
def send_notifications_multi(messages: list[dict]) -> str:
    """Sendet mehrere MQTT-Nachrichten in einem TCP-Connect — statt eines Connects pro Nachricht.

    Spart einen LLM-Roundtrip wenn mehrere Topics gleichzeitig adressiert werden müssen.
    Typischer Use-Case: Briefing-Push, das parallel auf das Live-Topic (retain=false) und
    den retained Cache-Topic geht.

    `messages` ist eine Liste von Dicts. Jedes Dict braucht/akzeptiert:
      - `topic`   (str, Pflicht): MQTT-Topic
      - `message` (str, Pflicht): Nachrichtentext
      - `retain`  (bool, optional, Default false)
      - `qos`     (int, optional, Default 0)
      - `title`   (str, optional): wenn gesetzt → Payload als JSON {"title", "message"}

    Beispiel:
      [
        {"topic": "claude/briefing/kamen",      "message": "Heute trüb..."},
        {"topic": "claude/briefing/kamen/text", "message": "Heute trüb...", "retain": true}
      ]
    """
    if not messages:
        return "⚠️ Keine Nachrichten übergeben."

    msgs = []
    for i, m in enumerate(messages):
        topic = m.get("topic")
        text = m.get("message")
        if not topic or text is None:
            return f"FEHLER: Element {i} braucht 'topic' und 'message': {m!r}"
        title = m.get("title")
        if title:
            payload = json.dumps({"title": title, "message": text}, ensure_ascii=False)
        else:
            payload = text
        msgs.append({
            "topic": topic,
            "payload": payload,
            "qos": int(m.get("qos", 0)),
            "retain": bool(m.get("retain", False)),
        })

    publish.multiple(
        msgs,
        hostname=MQTT_HOST,
        port=MQTT_PORT,
        auth=_auth(),
        tls=_tls(),
        client_id="claude-mqtt-notify",
        keepalive=10,
    )
    topics_str = ", ".join(m["topic"] for m in msgs)
    return f"📌 {len(msgs)} Nachrichten gesendet (1 TCP-Connect) → {topics_str}"


if __name__ == "__main__":
    mcp.run()
