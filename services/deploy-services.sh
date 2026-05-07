#!/usr/bin/env bash
# Deployt alle services/*.service nach /etc/systemd/system/.
# - kopiert nur Units, die sich tatsächlich unterscheiden
# - daemon-reload nur wenn etwas geändert wurde
# - restart von betroffenen Units, wenn sie aktiv oder enabled sind
#
# Aufruf:
#   sudo bash /home/claude/services/deploy-services.sh             # apply
#   bash /home/claude/services/deploy-services.sh --dry-run        # nur Diff
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DST_DIR=/etc/systemd/system
DRY_RUN=0

[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1
if [[ $DRY_RUN -eq 0 && $EUID -ne 0 ]]; then
  echo "ERR: bitte mit sudo starten (oder --dry-run fuer Vorschau)" >&2
  exit 1
fi

shopt -s nullglob
units=("$SRC_DIR"/*.service)
if [[ ${#units[@]} -eq 0 ]]; then
  echo "Keine *.service-Dateien in $SRC_DIR — nichts zu tun"
  exit 0
fi

changed=()

for src in "${units[@]}"; do
  name=$(basename "$src")
  dst="$DST_DIR/$name"

  if [[ -f "$dst" ]] && cmp -s "$src" "$dst"; then
    echo "= $name (unveraendert)"
    continue
  fi

  if [[ -f "$dst" ]]; then
    echo "~ $name (Diff vs. installiert):"
    diff -u "$dst" "$src" | sed 's/^/    /' || true
  else
    echo "+ $name (neu)"
  fi

  if [[ $DRY_RUN -eq 0 ]]; then
    install -m 0644 -o root -g root "$src" "$dst"
    changed+=("$name")
  fi
done

if [[ $DRY_RUN -eq 1 ]]; then
  echo ""
  echo "Dry-Run — keine Aenderungen geschrieben"
  exit 0
fi

if [[ ${#changed[@]} -eq 0 ]]; then
  echo "OK — keine Aenderungen"
  exit 0
fi

echo ""
echo "-> daemon-reload"
systemctl daemon-reload

for unit in "${changed[@]}"; do
  base="${unit%.service}"
  if systemctl is-active --quiet "$base" 2>/dev/null; then
    echo "-> restart $unit"
    systemctl restart "$base"
    echo "   $unit -> $(systemctl is-active "$base")"
  elif systemctl is-enabled --quiet "$base" 2>/dev/null; then
    echo "   $unit (enabled, aber inaktiv — kein restart)"
  else
    echo "   $unit (weder enabled noch aktiv — kein restart)"
  fi
done

echo "OK"
