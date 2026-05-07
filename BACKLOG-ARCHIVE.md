# Backlog Archive — /home/claude

Erledigte Tasks aus `BACKLOG.md`. Neueste oben. `BACKLOG.md` zeigt nur die jüngsten DONE-Items zur kurzen Historie; alle weiteren wandern hierher.

---

## 2026-05-07

### Git-Setup
- ✅ **Repository auf GitHub** (`kevinoehme/claude`) initialisiert. SSH-Auth via ed25519-Key (`~/.ssh/id_ed25519`), Public-Key auf GitHub eingetragen. Commit-Identität lokal gesetzt: `kevinoehme <54500193+kevinoehme@users.noreply.github.com>` (privacy-noreply). 24 Files initial gepusht.
- ✅ **`.gitignore` als Whitelist** (statt Blacklist) — schützt vor versehentlichem Commit von Secret-Stores (`.bashrc`, `.claude.json`, `.ssh/`), Caches (`.local/`, `.cache/`, `.npm/`), lokalen Daten (`data/`), Backup-Dateien (`*.bak.*`) und Maschinen-Overrides (`.claude/settings.local.json`).
- ✅ **README.md** mit Komponenten-Übersicht, Architektur-Embed-Link, Doku-Pointers (CLAUDE.md, BACKLOG.md, BACKLOG-ARCHIVE.md), Secrets-Hinweis.

### Latenz-Optimierung Briefing-Pipeline
- ✅ **Profiling-Layer** — `mcp/profiling.py` (atomares Append-Logging via `os.write` < PIPE_BUF) + `@profile`-Decorator auf alle Tools von `weather`, `abfall`, `mail_check`, `mqtt_notify` + `module_load`-Marker beim Server-Start. Profile-Log unter `/home/claude/data/profile.log`.
- ✅ **Latenz-Aufschlüsselung** (~33s pro Lauf gemessen): ~7% Cold-Start, ~29% Boot bis 1. Tool, ~5% eigentliche Tool-Calls, ~22% Briefing-Generation, ~10% Mehrfach-Push-Lücken, ~27% Cleanup. **Tool-Calls sind nicht der Engpass** — 87% sind LLM-Zeit.
- ✅ **Hebel 2 (deployed)** — `mqtt_notify.send_notifications_multi` (1 TCP-Connect für N Topics via `paho.publish.multiple`) + briefing-agent-Prompt auf 1 Push-Aufruf statt 2 umgestellt. Strukturell sichtbar im Profil (1 Tool-Call statt 2), gemessener Netto-Gewinn ~1.8s in Phase 4+5 — im Rauschen der Sonnet-Variance, aber sauberer.
- ❌ **Hebel 1 (verworfen)** — `claude -p --agent briefing-agent` testet Direkt-Subagent (Hauptmodell-Wrapper umgehen). Strukturell ~13s gespart in Phase 2+6, **aber +12s in Phase 4** (Sonnet als Top-Level langsamer als als Subagent — Hauptmodell wärmt offenbar Tool-Schema-Cache vor). Netto Wash → Code zurückgerollt zur Subagent-Variante.
- ✅ **Hebel 3 (vorbereitet)** — briefing-agent-Prompt von 111 → 101 Zeilen gestrafft (Verbotene-Muster-Liste komprimiert, Beispiele 3→2). Sauber-Messung steht aus → siehe Backlog N5.

### Auth & End-to-End-Verifikation
- ✅ **N2** — Diagnose: 39-Byte-stdout = `Invalid API key · Fix external API key`. Ursache via `/proc/<PID>/environ`-Inspektion + direkte API-Probe isoliert: Service-Env-Key war 103-char-Key mit HTTP 401, divergent zum 108-char-Key in `~/.bashrc`.
- ✅ **N3** — `services/sync_anthropic_key.sh` geschrieben (idempotent, atomar, kein Key-Echo via env-var an awk) und ausgeführt. Service läuft jetzt mit dem `~/.bashrc`-Key, API-Probe HTTP 200. Skript-Bug (Hash-Inkonsistenz `printf` vs `awk|sha256sum` durch trailing-newline) im selben Turn gefixt — `hash16()`-Helper für konsistente no-newline-Hashes.
- ✅ **N4** — End-to-End-Trigger nach Sync-Fix mehrfach verifiziert (`rc=0`, Alexa spricht). Latenz dabei gemessen → ~30–38s, Mittel ~34s.

### Doku & Tooling
- ✅ **B2** — `briefing-trigger`-Service neu gestartet (PID 5473 → 6315). Logging-Patch (stdout-Echo bei rc≠0) aktiviert, der die spätere Diagnose erst möglich machte.
- ✅ **O5** — `mcp/cron_record.py` als aktiv produktiv identifiziert (User-Crontab `5 * * * *`, schreibt sauber). In CLAUDE.md unter Sektion „Cron-Hilfsskript" dokumentiert; Architektur-Diagramm um Container „System Cron" + Box `cron_record.py` + Edges → openmeteo / sqlite erweitert.
- ✅ **O7** — `BACKLOG-ARCHIVE.md` angelegt, ältere DONE-Items dorthin ausgelagert.

### Secrets-Konsolidierung (zuvor)
- ✅ **O1** — Secret-Stores Hybrid-Konsolidierung: Inventar (3 Stores: `/etc/claude-secrets/briefing-trigger.env`, `.claude.json` MCP-env pro Projekt, `~/.bashrc` Legacy) inkl. Owner/Mode/Konsument/Backup-Hinweis in CLAUDE.md dokumentiert. Strategie B (pragmatisch): keine weitere Migration, jeder Store bleibt bei seinem Konsumenten.
- ✅ **B1** — Secrets-Migration durchgelaufen: `/etc/claude-secrets/briefing-trigger.env` aktiv, alte `/etc/default/briefing-trigger` weg, Service aktiv mit neuem `EnvironmentFile`.
- ✅ **N1 + O2** — End-to-End-Chain live verifiziert: Alexa-Sprachbefehl → HA-Skript → `…/request` → `briefing-trigger` → `claude -p` → `briefing-agent` → `…/kamen` (+ `/text`) → HA → Alexa-Ausgabe.
- ✅ Auto-Putze: `mcp/__pycache__/`, `services/__pycache__/`, alter `.claude.json.bak.1778157658` entfernt.
- ✅ Neuer Diagramm-Renderer `tools/drawio_render.py` (stdlib only, drawio→SVG). CLAUDE.md Architektur-Sektion um „Rendern"-Abschnitt erweitert.
- ✅ **O4** — `services/deploy-services.sh` geschrieben: idempotenter Rollout (cmp-s Diff-Erkennung, daemon-reload + restart nur bei Änderungen, --dry-run für Vorschau).
- ✅ **O3** — Diagramm-Restrukturierung: Container „Services (systemd)" um `briefing-trigger` (parallel zum CLI-Host-Container). MQTT-Mechanismen textlich differenziert. Legende um Container-Konvention + dreifache Edge-Differenzierung erweitert.
- ✅ Diagramm-Edge `ha → broker` (Trigger-Publish) ergänzt — Round-Trip visuell geschlossen.
- ✅ Migrations-Skript `services/migrate_secrets.sh` (idempotent, atomarer Filter+Move, sanity-checkt erwartete Keys, archiviert alte Datei als `.bak.<ts>`).
- ✅ Service-Template `services/briefing-trigger.service` auf neuen `EnvironmentFile`-Pfad.
- ✅ `services/briefing-trigger.env.example` Header-Kommentare auf neuen Zielpfad.
- ✅ `CLAUDE.md` Sektion „🔒 Secrets — niemals lesen, niemals echoen".
- ✅ Memory-Regel `feedback_no_read_secrets.md`.
- ✅ Memory-Regel `feedback_session_start_diagram.md` (Diagramm bei Sessionstart lesen).
