# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this directory is

`/home/claude/` is a personal Claude Code workspace, not a software project. It hosts custom MCP servers and Claude Code configuration for the user (located in Kamen, Germany). User-facing tool output is written in German throughout.

## Sessionstart — Pflicht-Reads

Bei jedem Sessionstart (oder wenn der User „weiter mit X" / „mach mal weiter" sagt ohne Verlauf) **zuerst** lesen, vor erster inhaltlicher Antwort:

1. **`/home/claude/BACKLOG.md`** — laufende Aufgabenliste mit Status (BLOCKED / NEXT / OPEN / DONE). Single Source of Truth für „was steht an".
2. **`/home/claude/architecture.drawio`** — aktuelle Architektur, fehlende/inkonsistente Edges sind oft Indikatoren für offene Arbeit.

Beide Dateien werden gemeinsam mit dem User gepflegt — Claude darf BACKLOG.md selbständig aktualisieren (Tasks ergänzen, Status ändern, Erledigtes nach DONE), das Diagramm nur bei strukturellen Änderungen wie in der Architektur-Pflege-Regel beschrieben.

## 🔒 Secrets — niemals lesen, niemals echoen

Alle Credentials (API-Keys, Mail-Passwörter, MQTT-Passwörter) liegen ausschließlich unter den folgenden drei Stores. Hybrid-Strategie: Service-Secrets sind zentral, User-Shell- und MCP-Embedded-Secrets bleiben bei ihrem Konsumenten — bei Restore alle drei wiederherstellen.

| # | Pfad | Owner / Mode | Schlüssel | Konsument |
|---|------|---|---|---|
| 1 | `/etc/claude-secrets/briefing-trigger.env` | `root:claude` / `0640` (Dir `0750`) | `MQTT_*`, `ANTHROPIC_API_KEY` | systemd-Unit `briefing-trigger.service` |
| 2 | `/home/claude/.claude.json` → `projects."/home/claude".mcpServers.<srv>.env` | `claude:claude` / `0600` | `email`/`mail_check`: `GMX_EMAIL`, `GMX_PASSWORD` · `mqtt_notify`: `MQTT_HOST/PORT/USER/PASSWORD` | Claude-Code-Host beim MCP-Server-Start (env an Subprozess) |
| 3 | `/home/claude/.bashrc` | `claude:claude` / `0644` | `ANTHROPIC_API_KEY` (Legacy-Export) | interaktive Shell beim Aufruf von `claude` CLI |

**Backup/Restore:** Alle drei Pfade müssen ins Backup. Ein Restore von nur Store 1 (Service-Secrets) reicht nicht — MCP-Server starten nicht ohne Store 2, interaktive `claude`-Shell ohne Store 3.

**Regeln:**
1. Diese Pfade NIEMALS mit `cat`, `Read`, `head`, `tail`, `less`, `grep -A/-B` o.ä. öffnen — auch nicht "kurz zur Diagnose". Der Inhalt landet sonst im Konversationsverlauf, der nicht rotiert werden kann.
2. Wenn du wissen musst, *ob* ein Key gesetzt ist: `grep -c '^KEY=' <datei>` oder `test -s <datei>` — nie den Wert lesen.
3. Wenn ein Wert geprüft werden muss (Format, Länge): die Variable in einer Subshell mit `awk` redaktieren (`awk -F= '{print $1"="substr($2,1,8)"…"}'`), nie den Roh-Wert ausgeben.
4. Migrationen / Umzüge von Secret-Files immer via Skript (siehe `services/migrate_secrets.sh`-Muster) — `sed`/`install` in einem privilegierten Skript, nie als Pipeline durch Claudes Tool-Output.
5. Beispiel-/Template-Dateien (`*.env.example`) gehören ins Repo und MÜSSEN Platzhalter (`sk-ant-…`) statt echter Werte enthalten.

## MCP servers (`/home/claude/mcp/`)

FastMCP servers, each runnable standalone via `python <file>.py`:

- **`weather.py`** — exposes `get_weather(city, country="DE", include_hourly=False)`, `get_weather_history(city, country="DE", days=7)` und `get_forecast_history(city, date, country="DE", hour=None)`. Two-step flow: Open-Meteo geocoding API → forecast API. Returns current conditions plus 3-day and 7-day outlook; with `include_hourly=True` zusätzlich stündlich für heute. Every successful `get_weather` call persists current/daily (and hourly when requested) into the SQLite DB via `db.py`. WMO weather codes are translated to German via an inline `wmo` dict; extend that dict when adding codes.
- **`abfall.py`** — Müllkalender für Kiebitzweg 12, 59174 Kamen. Exposes `get_next_pickup()`, `get_pickups(days=14)`, `get_pickups_by_type(waste_type)`. Nutzt die regioit-API (`https://abfallapp.regioit.de/abfall-app-unna/rest`) der GWA Kreis Unna. `STREET_ID` und `USER_BIN_FRAKTIONEN` sind im Modul hardcoded (Restmüll=0, Bio=4, Papier=5, Gelbe Tonne=6). API-Termine werden in der SQLite-DB gecached (`abfall_pickups`-Tabelle); Refresh erfolgt automatisch wenn der Cache älter als `CACHE_MAX_AGE_HOURS` (24 h) ist.
- **`db.py`** — SQLite-Persistenz unter `/home/claude/data/weather.db`. Schema: `locations`, `current_observations`, `daily_forecasts`, `hourly_forecasts` (Wetter), `abfall_pickups` (Müllkalender, UNIQUE auf `(pickup_date, fraktion_id)`) und `mail_state` (Mail-Polling, PK auf `account`, speichert `last_seen_uid`). `init_db()` läuft beim Import von `weather.py`, `abfall.py` und `mail_check.py`. DB-Schreibfehler werden geloggt, aber nicht propagiert — der Tool-Aufruf bleibt funktionsfähig.
- **`gmx_mail.py`** — exposes `get_emails(count)` and `get_email_body(index)`. IMAP against `imap.gmx.net:993`. Indices are 1-based and count back from newest, so `index=1` is the latest message. Each call opens and tears down its own IMAP session. Reads credentials from `GMX_EMAIL` / `GMX_PASSWORD` at import time — will crash on import if those env vars aren't set, so the launching MCP client must inject them.
- **`mail_check.py`** — Mail-Polling-Server für automatisierte Notifications (vom `briefing-agent` genutzt). Exposes `get_new_emails(max_report=10)` und `reset_mail_baseline()`. Nutzt UID-basierten IMAP-Search und persistiert `last_seen_uid` in der `mail_state`-Tabelle. **Erstlauf** setzt nur die Baseline (keine Backlog-Flut), danach werden nur neue UIDs gemeldet. Liest dieselben `GMX_EMAIL` / `GMX_PASSWORD`-Env-Vars wie `gmx_mail.py`. Falls IMAP-`UIDVALIDITY` sich serverseitig ändert, sieht der nächste Lauf alle Mails als "neu" — dann manuell `reset_mail_baseline()` aufrufen.
- **`mqtt_notify.py`** — generischer MQTT-Notification-Channel (von beliebigen Agents/Tools nutzbar). Zwei Tools:
  - `send_notification(message, topic=None, title=None, retain=False, qos=0)` — Single-Topic-Push via `publish.single()` (1 Connect pro Aufruf).
  - `send_notifications_multi(messages: list[dict])` — Multi-Topic-Push via `publish.multiple()` (1 Connect für N Topics). Spart einen LLM-Roundtrip wenn dieselbe oder verschiedene Nachrichten parallel an mehrere Topics müssen (Briefing-Pattern: Live-Topic retain=false + Cache-Topic retain=true). Jedes `messages`-Element: `{topic, message, retain?, qos?, title?}`.

  Env-Vars: `MQTT_HOST` (Pflicht), `MQTT_PORT` (Default 1883), `MQTT_USER`/`MQTT_PASSWORD` (optional), `MQTT_DEFAULT_TOPIC` (Default `claude/notifications`), `MQTT_TLS=1` für TLS. Mit `title` wird Payload als JSON `{"title", "message"}` gesendet, sonst Plain-Text. Home Assistant abonniert die Topics und routet z.B. nach Alexa Echo Dot.
- **`profiling.py`** — Cross-cutting Diagnose-Modul. Stellt `module_load(server)` (Marker beim MCP-Server-Import) und `@profile(label)` (Decorator um `@mcp.tool`-Funktionen) bereit. Schreibt atomar nach `/home/claude/data/profile.log` (`os.write` < PIPE_BUF). Genutzt zur Latenz-Analyse der Briefing-Pipeline (Cold-Start, Tool-Reihenfolge, Tool-Dauer). Aktiv in `weather.py`, `abfall.py`, `mail_check.py`, `mqtt_notify.py`. Kein FastMCP-Server — wird nicht im Architektur-Diagramm gerendert. Kann ohne Funktionsänderung wieder entfernt werden, sobald nicht mehr gebraucht.

### Cron-Hilfsskript (kein MCP, liegt aus historischen Gründen im selben Ordner)

- **`cron_record.py`** — Standalone-Skript, kein FastMCP-Server. Wird von der User-Crontab stündlich aufgerufen (`5 * * * * /usr/bin/python3 /home/claude/mcp/cron_record.py`), um Wetterdaten für Kamen unabhängig vom MCP-Host in die SQLite-DB zu schreiben. Loggt Erfolg/Fehler nach `/home/claude/data/cron.log`. Zwei externe Calls (Open-Meteo geocoding + forecast), dann `db.upsert_location` / `record_current` / `record_daily` / `record_hourly` über `db.py`. Wenn der MCP-Host läuft, schreibt zusätzlich `weather.py` bei jedem `get_weather`-Aufruf — Cron sorgt für Backfill, wenn die Hauptsession aus ist. Cron-Eintrag pflegen via `crontab -e -u claude`.

## Standalone-Services (`/home/claude/services/`)

Längerlaufende Hintergrund-Prozesse — keine MCPs, sondern systemd-Units, die per MQTT ein- und ausgehende Brücken zwischen Home Assistant und Claude Code bilden.

- **`briefing_trigger.py` + `briefing-trigger.service`** — MQTT-Listener, der bei Nachrichten auf `claude/briefing/kamen/request` einen Headless-`claude -p`-Lauf startet. Damit kann Home Assistant per `mqtt.publish` (z.B. nach einem Alexa-Sprachbefehl) den `briefing-agent` triggern, ohne SSH oder HTTP-Endpoints. Nutzt dieselben `MQTT_*`-Env-Vars wie `mqtt_notify.py`. Ein `threading.Lock` verhindert überlappende Läufe (Trigger während laufendem Briefing wird verworfen). Config: `/etc/claude-secrets/briefing-trigger.env` (Beispiel: `/home/claude/services/briefing-trigger.env.example`). Logs via `journalctl -u briefing-trigger`.
- **`deploy-services.sh`** — kopiert idempotent alle `services/*.service` nach `/etc/systemd/system/`. Erkennt Diff (`cmp -s`), macht `daemon-reload` + `restart` nur bei tatsächlichen Änderungen. Aufruf: `sudo bash /home/claude/services/deploy-services.sh` (oder `--dry-run` für Vorschau). Repo-Unit-File ist Single Source of Truth — nie direkt am installierten Unit `sed`-en.
- **`sync_anthropic_key.sh`** — gleicht den `ANTHROPIC_API_KEY` zwischen `~/.bashrc` (Store 3, Legacy-Export) und `/etc/claude-secrets/briefing-trigger.env` (Store 1, Service-Env) ab. Liest Key per awk aus `~/.bashrc`, vergleicht Hashes, ersetzt im env-File atomar (mit Backup `*.bak.<ts>`), restartet `briefing-trigger` und verifiziert über `/proc/<PID>/environ`-Hash. Idempotent (no-op bei Gleichstand). Kein Key-Echo in stdout/History — Wert wird via Env-Var an awk übergeben. Aufruf: `sudo bash /home/claude/services/sync_anthropic_key.sh`. Nutzen, wenn der Service mit `Invalid API key` ausfällt (siehe Backlog N3).

## Claude Code configuration (`/home/claude/.claude/`)

- **`agents/briefing-agent.md`** — subagent that combines weather (`mcp__weather__*`), waste collection (`mcp__abfall__*`) und Mail-Check (`mcp__mail_check__get_new_emails`) into a short German daily briefing for Kamen / Kiebitzweg, then pushes the briefing via **`mcp__mqtt_notify__send_notifications_multi`** in einem einzigen Aufruf an zwei MQTT-Topics: `claude/briefing/kamen` (`retain=false`, sofortige Alexa-Wiedergabe — retain=true würde bei MQTT-Reconnects erneut vorgelesen) und `claude/briefing/kamen/text` (`retain=true`, on-demand Cache für Sprachbefehl). Runs on **Sonnet** (`model: sonnet` im Frontmatter — Haiku wäre schneller, opfert aber Tonfall-Qualität). Format and decision thresholds (rain >5 mm, min <5 °C, max >25 °C, "Tonne raus" wenn morgen Abholung, Mail-Hinweis nur bei echten neuen Mails) are defined in the agent's prompt — change them there, not in `weather.py` / `abfall.py` / `mail_check.py`.
- **`settings.local.json`** — pre-allows `mcp__weather__*`, `mcp__email__get_emails`, `mcp__mail_check__*`, `mcp__mqtt_notify__send_notification`, `mcp__mqtt_notify__send_notifications_multi` und `mcp__abfall__*` so they don't prompt. Add new allow entries here when adding tools that should run unattended (e.g. via `briefing-agent` or scheduled jobs). **Wird nicht ins Git-Repo eingecheckt** (Konvention: `.local.json`-Suffix → maschinen-spezifische Permission-Whitelist; `.gitignore` schließt es aus).
- **`settings.json`** — global settings (theme, `permissions.defaultMode: acceptEdits`).

## Working on the MCP servers

- The servers are not registered in this repo's settings; their MCP client registration lives elsewhere. After editing a server, the user needs to restart their Claude Code session (or the MCP host) for changes to take effect — there is no hot reload.
- All user-visible strings are German. Keep new strings consistent with the existing tone (concise, emoji headers like `📍 📅 📬 📌`, `=`/`─` separators).
- No tests, no linter, no build step. Validate changes by running `python /home/claude/mcp/<file>.py` and confirming it starts without errors, or by invoking the tool through the MCP client.

## Architektur-Diagramm (`/home/claude/architecture.drawio`)

**Pflicht:** Diese Datei ist die Single Source of Truth für die Architektur (LLM ↔ Agents ↔ MCP-Server ↔ Tools ↔ External APIs ↔ Storage ↔ Notification-Pipeline) und MUSS bei jeder relevanten Änderung im selben Turn mitgepflegt werden. Auslöser:

- Neuer / entfernter / umbenannter MCP-Server unter `/home/claude/mcp/`
- Neues / entferntes Tool (FastMCP `@mcp.tool`) in einem bestehenden Server
- Neuer / entfernter Agent unter `/home/claude/.claude/agents/`
- Geänderter Datenfluss (neuer External-API-Endpoint, neues DB-Schema, neuer MQTT-Topic, neuer Notification-Sink)
- Neue LLM-Rolle (z. B. anderer Subagent-Modell-Pin)

**Workflow bei Änderungen:** zuerst Code anpassen → unmittelbar danach `architecture.drawio` updaten (Boxen, Edges, ggf. Legende) → dann CLAUDE.md falls nötig nachziehen. Niemals Code-Änderung committen ohne synchrones Diagramm-Update.

**Failsafe:** Ein PostToolUse-Hook (`/home/claude/.claude/hooks/architecture_diagram_reminder.py`, in `settings.json` unter `hooks.PostToolUse` registriert) feuert bei jedem Edit/Write/MultiEdit/NotebookEdit auf `/home/claude/mcp/*` oder `/home/claude/.claude/agents/*` und injiziert einen Reminder ins Context-Window. Wenn der Reminder erscheint und keine Diagramm-Änderung nötig ist (z. B. reines Bugfix ohne Strukturänderung), das kurz im Turn begründen statt stillschweigend ignorieren.

**Rendern:** `python3 /home/claude/tools/drawio_render.py` erzeugt aus dem `.drawio`-XML eine `architecture.svg` (stdlib only, kein Drawio-CLI nötig). Versteht nur die in unserem Diagramm verwendeten Style-Attribute (fillColor, strokeColor, dashed, fontSize, fontStyle, rounded, verticalAlign, align). Container werden per Geometrie-Heuristik erkannt und zuerst gerendert (Z-Order). Bei drastisch neuen Style-Konstrukten (z. B. mxPoint-Routing, Shapes außer Rechteck) muss der Renderer nachgezogen werden.
