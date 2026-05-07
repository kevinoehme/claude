#!/usr/bin/env bash
# Einmaliger / wiederholbarer Sync:
#   ANTHROPIC_API_KEY in ~/.bashrc (Store 3, Legacy-Export)
#   →  /etc/claude-secrets/briefing-trigger.env (Store 1, Service-Env)
#
# Hintergrund: die zwei Secret-Stores sind aus dem Sync gelaufen.
# Service-Env-Key wurde als invalid (HTTP 401) verifiziert, .bashrc-Key
# läuft sauber (interaktive claude-Session). Dieses Skript hebt die
# Divergenz auf, ohne den Key in Tool-Output / Shell-History echoen zu müssen.
#
# Aufruf:   sudo bash /home/claude/services/sync_anthropic_key.sh
#
# Idempotent: wenn die Keys schon übereinstimmen, no-op (Service wird
# nicht unnötig neu gestartet).
set -euo pipefail

BASHRC=/home/claude/.bashrc
DST=/etc/claude-secrets/briefing-trigger.env

[[ $EUID -eq 0 ]] || { echo "ERR: bitte mit sudo starten"; exit 1; }
[[ -r "$BASHRC" ]] || { echo "ERR: $BASHRC nicht lesbar"; exit 1; }
[[ -f "$DST" ]] || { echo "ERR: $DST fehlt"; exit 1; }

# Key aus ~/.bashrc extrahieren — ohne Echo in stdout
NEW_KEY=$(awk '
  /^[[:space:]]*export[[:space:]]+ANTHROPIC_API_KEY=/ {
    v=$0
    sub(/^[[:space:]]*export[[:space:]]+ANTHROPIC_API_KEY=/, "", v)
    gsub(/^["\x27]/, "", v)
    gsub(/["\x27]$/, "", v)
    print v
    exit
  }' "$BASHRC")

if [[ -z "$NEW_KEY" ]]; then
  echo "ERR: kein ANTHROPIC_API_KEY-Export in $BASHRC gefunden"
  exit 1
fi

# Sanity-Format (no value echo)
if [[ ! "$NEW_KEY" =~ ^sk-ant- ]]; then
  echo "ERR: Key in $BASHRC sieht nicht wie ein Anthropic-Key aus (Prefix != sk-ant-)"
  exit 1
fi

# Hash-Helper: konsistent ohne trailing-newline hashen, sonst hash($value) ≠ hash($value+\n)
hash16() { printf '%s' "$1" | sha256sum | cut -c1-16; }

OLD_KEY=$(awk -F= '/^ANTHROPIC_API_KEY=/{sub(/^[^=]*=/,""); print; exit}' "$DST")
H_NEW=$(hash16 "$NEW_KEY")
H_OLD=$(hash16 "$OLD_KEY")
unset OLD_KEY
echo "  bashrc  sha256-16: $H_NEW"
echo "  env     sha256-16: $H_OLD"

if [[ "$H_NEW" == "$H_OLD" ]]; then
  echo "OK — keys identisch, kein Update nötig"
  exit 0
fi

# Atomares Replace: temp-File schreiben, dann install (preserve mode/owner)
TMP=$(mktemp /etc/claude-secrets/.briefing-trigger.env.XXXXXX)
trap 'rm -f "$TMP"' EXIT

# bestehende Datei kopieren, ANTHROPIC_API_KEY-Zeile durch neuen Wert ersetzen.
# Wert wird per ENV-Var an awk übergeben (nicht via Cmdline-Arg → keine
# Sichtbarkeit in /proc/<pid>/cmdline und kein Eintrag in History).
NEW_KEY="$NEW_KEY" awk '
  BEGIN { k = ENVIRON["NEW_KEY"]; replaced = 0 }
  /^ANTHROPIC_API_KEY=/ {
    if (!replaced) { print "ANTHROPIC_API_KEY=" k; replaced = 1; next }
  }
  { print }
  END {
    if (!replaced) { print "ANTHROPIC_API_KEY=" k > "/dev/stderr"; exit 2 }
  }' "$DST" > "$TMP"

# Mode/Owner vom Original übernehmen
chown --reference="$DST" "$TMP"
chmod --reference="$DST" "$TMP"

# Backup + atomar move
TS=$(date +%Y%m%d-%H%M%S)
cp -p "$DST" "${DST}.bak.${TS}"
mv "$TMP" "$DST"
trap - EXIT

echo "  Backup:     ${DST}.bak.${TS}"

systemctl restart briefing-trigger
sleep 1
STATE=$(systemctl is-active briefing-trigger)
echo "  Service:    $STATE"

unset NEW_KEY

# Sanity: Key im neuen Service-Prozess vorhanden, Hash matcht (no trailing-newline)
PID=$(systemctl show -p MainPID --value briefing-trigger)
PROC_KEY=$(tr '\0' '\n' < /proc/$PID/environ | awk -F= '/^ANTHROPIC_API_KEY=/{sub(/^[^=]*=/,""); print; exit}')
H_PROC=$(hash16 "$PROC_KEY")
unset PROC_KEY
echo "  proc-env sha256-16: $H_PROC"
[[ "$H_PROC" == "$H_NEW" ]] && echo "OK — Service läuft mit neuem Key" || { echo "ERR — Service-Env nicht aktualisiert"; exit 1; }
