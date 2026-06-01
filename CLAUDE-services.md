# CLAUDE-services.md

Detail-Doku zu den systemd-Services und Helper-Skripten unter `/home/claude/services/`. Wird **nicht** automatisch in den Session-Kontext geladen — nur lesen, wenn du an einem dieser Services arbeitest oder die Briefing-Trigger-Pipeline debuggen musst.

## Standalone-Services (`/home/claude/services/`)

Längerlaufende Hintergrund-Prozesse — keine MCPs, sondern systemd-Units, die per MQTT ein- und ausgehende Brücken zwischen Home Assistant und Claude Code bilden.

- **`briefing_trigger.py` + `briefing-trigger.service`** — MQTT-Listener, der bei Nachrichten auf `claude/briefing/kamen/request` einen Headless-`claude -p`-Lauf startet. Damit kann Home Assistant per `mqtt.publish` (z.B. nach einem Alexa-Sprachbefehl) den `briefing-agent` triggern, ohne SSH oder HTTP-Endpoints. Nutzt dieselben `MQTT_*`-Env-Vars wie `mqtt_notify.py`. Ein `threading.Lock` verhindert überlappende Läufe (Trigger während laufendem Briefing wird verworfen). Config: `/etc/claude-secrets/briefing-trigger.env` (Beispiel: `/home/claude/services/briefing-trigger.env.example`). Logs via `journalctl -u briefing-trigger`.
- **`deploy-services.sh`** — kopiert idempotent alle `services/*.service` nach `/etc/systemd/system/`. Erkennt Diff (`cmp -s`), macht `daemon-reload` + `restart` nur bei tatsächlichen Änderungen. Aufruf: `sudo bash /home/claude/services/deploy-services.sh` (oder `--dry-run` für Vorschau). Repo-Unit-File ist Single Source of Truth — nie direkt am installierten Unit `sed`-en.
- **`sync_anthropic_key.sh`** — gleicht den `ANTHROPIC_API_KEY` zwischen `~/.bashrc` (Store 3, Legacy-Export) und `/etc/claude-secrets/briefing-trigger.env` (Store 1, Service-Env) ab. Liest Key per awk aus `~/.bashrc`, vergleicht Hashes, ersetzt im env-File atomar (mit Backup `*.bak.<ts>`), restartet `briefing-trigger` und verifiziert über `/proc/<PID>/environ`-Hash. Idempotent (no-op bei Gleichstand). Kein Key-Echo in stdout/History — Wert wird via Env-Var an awk übergeben. Aufruf: `sudo bash /home/claude/services/sync_anthropic_key.sh`. Nutzen, wenn der Service mit `Invalid API key` ausfällt (siehe Backlog N3).
