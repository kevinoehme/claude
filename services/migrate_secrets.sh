#!/usr/bin/env bash
# Einmalige Migration:
#   /etc/default/briefing-trigger  →  /etc/claude-secrets/briefing-trigger.env
#
# - räumt Heredoc-Reste (EOF/chmod/chown/ls) aus der Env-Datei
# - strippt führendes Whitespace
# - legt /etc/claude-secrets/ als kanonischen Secrets-Ort an (0750 root:claude)
# - patcht das systemd-Unit auf den neuen EnvironmentFile-Pfad
# - reload + restart
#
# Aufruf:   sudo bash /home/claude/services/migrate_secrets.sh
set -euo pipefail

SRC=/etc/default/briefing-trigger
DST_DIR=/etc/claude-secrets
DST=$DST_DIR/briefing-trigger.env
UNIT=/etc/systemd/system/briefing-trigger.service

[[ $EUID -eq 0 ]] || { echo "ERR: bitte mit sudo starten"; exit 1; }
[[ -r "$SRC" ]] || { echo "ERR: $SRC nicht lesbar"; exit 1; }
[[ -f "$UNIT" ]] || { echo "ERR: $UNIT fehlt"; exit 1; }

install -d -m 0750 -o root -g claude "$DST_DIR"

# Filter: nur KEY=VALUE / Kommentar / Leerzeile durchlassen, führendes Whitespace weg
sed -E '
  s/^[[:space:]]+//;
  /^([A-Z_][A-Z0-9_]*=|#|$)/!d
' "$SRC" > "$DST.new"

# Sanity: erwartete Keys vorhanden
for k in MQTT_HOST MQTT_USER ANTHROPIC_API_KEY; do
  grep -q "^${k}=" "$DST.new" || { echo "ERR: ${k} fehlt nach Filter"; rm -f "$DST.new"; exit 1; }
done

install -m 0640 -o root -g claude "$DST.new" "$DST"
rm -f "$DST.new"

# systemd-Unit auf neuen Pfad zeigen lassen (idempotent)
if grep -q '^EnvironmentFile=/etc/default/briefing-trigger$' "$UNIT"; then
  sed -i 's|^EnvironmentFile=/etc/default/briefing-trigger$|EnvironmentFile=/etc/claude-secrets/briefing-trigger.env|' "$UNIT"
fi

systemctl daemon-reload
systemctl restart briefing-trigger
sleep 1
systemctl is-active briefing-trigger

# Alte Datei archivieren (nicht löschen — als Backup)
TS=$(date +%Y%m%d-%H%M%S)
mv "$SRC" "${SRC}.bak.${TS}"
chmod 0600 "${SRC}.bak.${TS}"

echo "OK"
echo "  Secrets:    $DST  (0640 root:claude)"
echo "  Backup:     ${SRC}.bak.${TS}"
echo "  Service:    $(systemctl is-active briefing-trigger)"
