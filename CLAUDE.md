# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this directory is

`/home/claude/` is a personal Claude Code workspace, not a software project. It hosts custom MCP servers and Claude Code configuration for the user (located in Kamen, Germany — PLZ 59174). User-facing tool output is written in German throughout.

**Adress-Privatsphäre:** Straße und Hausnummer dürfen nirgends im Repo, in Logs, in Tool-Output oder im Konversationsverlauf auftauchen. Sie liegen ausschließlich in der lokalen, gitignorierten Config `/home/claude/data/location.json` (Template: `mcp/location.json.example`). Stadt + PLZ sind öffentlich und dürfen im Code stehen.

## Sessionstart — Pflicht-Reads

Bei jedem Sessionstart (oder wenn der User „weiter mit X" / „mach mal weiter" sagt ohne Verlauf) **zuerst** lesen, vor erster inhaltlicher Antwort:

1. **`/home/claude/BACKLOG.md`** — laufende Aufgabenliste mit Status (BLOCKED / NEXT / OPEN / DONE). Single Source of Truth für „was steht an".

Claude darf BACKLOG.md selbständig aktualisieren (Tasks ergänzen, Status ändern, Erledigtes nach DONE).

**Nicht** auto-lesen: `architecture.drawio` (~1-4 k Tokens XML pro Session) — nur on-demand bei strukturellen Architektur-Änderungen, siehe `CLAUDE-workflow.md`. Für reine Tool-Inhaltsfragen reicht das Routing unten.

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

## Routing: wo steht was

Diese CLAUDE.md ist der Einstieg. Detail-Doku ist nach Themengebieten getrennt — **lies das passende File on-demand, statt alle bei Sessionstart zu laden**.

| Wenn du arbeitest an … | Lies (via Read-Tool) |
|---|---|
| MCP-Servern unter `mcp/` (Tools, Signaturen, DB-Schema, Mail/Wetter/Abfall/MQTT-Logik) · `cron_record.py` | **`/home/claude/CLAUDE-mcp.md`** |
| systemd-Units unter `services/` · Briefing-Trigger-Pipeline · `deploy-services.sh` · `sync_anthropic_key.sh` | **`/home/claude/CLAUDE-services.md`** |
| `briefing-agent.md` · `settings.json` / `settings.local.json` · Architektur-Diagramm-Pflege · Diagramm-Renderer | **`/home/claude/CLAUDE-workflow.md`** |
| Strukturellen Architektur-Änderungen (neuer MCP-Server / Agent / Datenfluss) | `CLAUDE-workflow.md` **und** `architecture.drawio` |

Wenn die Aufgabe mehrere Bereiche berührt: alle passenden Files lesen, parallel.

## Top-Level-Files im Repo

- `BACKLOG.md` / `BACKLOG-ARCHIVE.md` — aktive Aufgaben + Historie
- `README.md` — High-Level-Pitch + Komponenten-Übersicht (Mensch-Doku)
- `architecture.drawio` / `architecture.svg` — Architektur-Diagramm (Source + Render)
- `mcp/location.json.example` — Template für die lokale Adress-Config (echte Werte: `data/location.json`, gitignored)
