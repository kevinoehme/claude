# claude

Persönlicher Claude-Code-Workspace für **Kamen, NRW (PLZ 59174)**.
Kombiniert mehrere Custom-MCP-Server, einen Tagesbriefing-Subagent und einen
MQTT-getriggerten systemd-Service zu einer Sprach-Pipeline:

> Alexa „Briefing" → Home Assistant → MQTT → systemd-Listener → headless `claude -p`
> → briefing-agent (Sonnet) → Wetter + Abfall + Mail → MQTT → Home Assistant → Alexa-TTS

Zweck: morgens auf Zuruf eine kurze, gesprochene Lage-Einschätzung
(Wetter, Müllabholung, neue E-Mails, Empfehlung) — ohne Smartphone, ohne UI.

## Architektur

Vollständiges Diagramm: [`architecture.svg`](architecture.svg)
(Quelle: [`architecture.drawio`](architecture.drawio), gerendert via
`tools/drawio_render.py` — stdlib-only, kein draw.io-CLI nötig).

## Komponenten

- **[`mcp/`](mcp/)** — FastMCP-Server, jeweils einzeln startbar via `python <file>.py`:
  - `weather.py` (Open-Meteo, Forecast + History, persistiert nach SQLite)
  - `abfall.py` (regioit GWA Kreis Unna, 24 h Cache)
  - `mail_check.py` (UID-basiertes IMAP-Polling, baseline-aware)
  - `gmx_mail.py` (Ad-hoc-Mail-Lesen)
  - `mqtt_notify.py` (Single- + Multi-Topic-Push)
  - `db.py` (gemeinsame SQLite-Schicht)
  - `profiling.py` (Cross-cutting Latenz-Diagnose)
  - `cron_record.py` (Stündliches Wetter-Backfill via crontab)

- **[`services/`](services/)** — systemd-Units + Helfer:
  - `briefing_trigger.py` + `briefing-trigger.service` — MQTT-Listener,
    der `claude/briefing/kamen/request` abonniert und einen headless
    `claude -p`-Lauf startet.
  - `deploy-services.sh` — idempotenter Unit-Rollout.
  - `migrate_secrets.sh` — Einmal-Migration des EnvironmentFile-Pfads.
  - `sync_anthropic_key.sh` — Sync zwischen Secret-Stores ohne Key-Echo.

- **[`.claude/agents/briefing-agent.md`](.claude/agents/briefing-agent.md)** —
  der Subagent-Prompt: Tonfall-Anker, Tool-Pflichtaufrufe, Mail-/Müll-/Wetter-Regeln.

- **[`tools/drawio_render.py`](tools/drawio_render.py)** — Renderer drawio→SVG.

## Doku & Status

- **[`CLAUDE.md`](CLAUDE.md)** — vollständige technische Referenz: alle
  Tools im Detail, Secrets-Strategie (3-Stores-Hybrid), Architektur-Pflege-Regel,
  Validierungs-Workflow.
- **[`BACKLOG.md`](BACKLOG.md)** — laufende Aufgaben mit Status (`BLOCKED` /
  `NEXT` / `OPEN` / `DONE`).
- **[`BACKLOG-ARCHIVE.md`](BACKLOG-ARCHIVE.md)** — Historie erledigter Tasks.

## Secrets

Werden **nirgendwo im Repo** gespeichert. Die `.gitignore` ist als Whitelist
implementiert (alles ignoriert, gezielt erlaubt) — schützt vor versehentlichem
Commit von `.bashrc`, `.claude.json`, `.ssh/`, `data/`. Details zur
3-Stores-Hybrid-Strategie in `CLAUDE.md`.
