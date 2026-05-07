# Backlog Archive — /home/claude

Erledigte Tasks aus `BACKLOG.md`. Neueste oben. `BACKLOG.md` behält nur die jüngsten ~3 DONE-Items zur kurzen Historie, danach wandern sie hierher.

---

## 2026-05-07

- ✅ **O7** — DONE-Liste in `BACKLOG-ARCHIVE.md` ausgelagert. Diese Datei angelegt; `BACKLOG.md` zeigt nur noch die jüngsten DONE-Items zur Kurz-Historie.
- ✅ **O5** — `mcp/cron_record.py` als aktiv produktiv identifiziert (User-Crontab `5 * * * *`, schreibt sauber in `cron.log` + SQLite). In CLAUDE.md unter neuer Sektion „Cron-Hilfsskript" dokumentiert; Architektur-Diagramm um Container „System Cron" + Box `cron_record.py` + Edges → openmeteo / sqlite erweitert. Legende auf „MCP-Server / Standalone-Skript" und „systemd Services / System Cron" erweitert.
- ✅ **B2** — `briefing-trigger`-Service neu gestartet (PID-Wechsel 5473 → 6315, ActiveEnterTimestamp 19:41:40 UTC). Logging-Patch (stdout-Echo bei rc≠0) damit aktiv.
- ✅ **O1** — Secret-Stores Hybrid-Konsolidierung: Inventar (3 Stores: `/etc/claude-secrets/briefing-trigger.env`, `.claude.json` MCP-env pro Projekt, `~/.bashrc` Legacy) inkl. Owner/Mode/Konsument/Backup-Hinweis in CLAUDE.md dokumentiert. Strategie B (pragmatisch): keine weitere Migration, jeder Store bleibt bei seinem Konsumenten.
- ✅ **B1** — Secrets-Migration durchgelaufen: `/etc/claude-secrets/briefing-trigger.env` aktiv, alte `/etc/default/briefing-trigger` weg, Service aktiv mit neuem `EnvironmentFile`.
- ✅ **N1 + O2** — End-to-End-Chain live verifiziert: Alexa-Sprachbefehl → HA-Skript → `…/request` → `briefing-trigger` → `claude -p` → `briefing-agent` → `…/kamen` (+ `/text`) → HA → Alexa-Ausgabe. User-Bestätigung: „ausgabe war OK".
- ✅ Auto-Putze: `mcp/__pycache__/`, `services/__pycache__/`, alter `.claude.json.bak.1778157658` entfernt (~104 KB).
- ✅ Neuer Diagramm-Renderer `tools/drawio_render.py` (stdlib only, drawio→SVG). CLAUDE.md Architektur-Sektion um „Rendern"-Abschnitt erweitert.
- ✅ **O4** — `services/deploy-services.sh` geschrieben: idempotenter Rollout (cmp-s Diff-Erkennung, daemon-reload + restart nur bei Änderungen, --dry-run für Vorschau). CLAUDE.md `services/`-Sektion um diesen Helfer erweitert. Nebeneffekt: `Config:`-Pfad in CLAUDE.md vom alten `/etc/default/briefing-trigger` auf `/etc/claude-secrets/briefing-trigger.env` korrigiert.
- ✅ **O3** — Diagramm-Restrukturierung: neuer Container „Services (systemd)" um `briefing-trigger` (beige, parallel zum CLI-Host-Container). MQTT-Mechanismen textlich differenziert: `mqtt_notify.py` „publish.single, one-shot connect" vs `briefing-trigger` „persistent mqtt.Client loop". Legende um Container-Konvention + dreifache Edge-Differenzierung erweitert.
- ✅ Diagramm-Edge `ha → broker` (Trigger-Publish) ergänzt — Round-Trip jetzt visuell geschlossen.
- ✅ Migrations-Skript `services/migrate_secrets.sh` geschrieben (idempotent, atomarer Filter+Move, sanity-checkt erwartete Keys, archiviert alte Datei als `.bak.<ts>`).
- ✅ Service-Template `services/briefing-trigger.service` auf neuen `EnvironmentFile`-Pfad.
- ✅ `services/briefing-trigger.env.example` Header-Kommentare auf neuen Zielpfad.
- ✅ `CLAUDE.md` Sektion „🔒 Secrets — niemals lesen, niemals echoen".
- ✅ Memory-Regel `feedback_no_read_secrets.md`.
- ✅ Memory-Regel `feedback_session_start_diagram.md` (Diagramm bei Sessionstart lesen).
