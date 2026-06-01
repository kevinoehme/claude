# CLAUDE-workflow.md

Detail-Doku zu Claude-Code-Konfiguration, Architektur-Pflege-Regel und Diagramm-Renderer. Wird **nicht** automatisch in den Session-Kontext geladen — lesen, wenn:

- du am `briefing-agent` oder an einer settings-Datei arbeitest,
- die Architektur strukturell geändert wird (neuer MCP-Server, neuer Agent, neuer Datenfluss) → der hier definierte Workflow MUSS dann eingehalten werden,
- der Diagramm-Renderer angepasst werden soll.

## Claude Code configuration (`/home/claude/.claude/`)

- **`agents/briefing-agent.md`** — subagent that combines weather (`mcp__weather__*`), waste collection (`mcp__abfall__*`) und Mail-Check (`mcp__mail_check__get_new_emails`) into a short German daily briefing for Kamen, then pushes the briefing via **`mcp__mqtt_notify__send_notifications_multi`** in einem einzigen Aufruf an zwei MQTT-Topics: `claude/briefing/kamen` (`retain=false`, sofortige Alexa-Wiedergabe — retain=true würde bei MQTT-Reconnects erneut vorgelesen) und `claude/briefing/kamen/text` (`retain=true`, on-demand Cache für Sprachbefehl). Runs on **Sonnet** (`model: sonnet` im Frontmatter — Haiku wäre schneller, opfert aber Tonfall-Qualität). Format and decision thresholds (rain >5 mm, min <5 °C, max >25 °C, "Tonne raus" wenn morgen Abholung, Mail-Hinweis nur bei echten neuen Mails) are defined in the agent's prompt — change them there, not in `weather.py` / `abfall.py` / `mail_check.py`.
- **`settings.local.json`** — pre-allows `mcp__weather__*`, `mcp__email__get_emails`, `mcp__mail_check__*`, `mcp__mqtt_notify__send_notification`, `mcp__mqtt_notify__send_notifications_multi` und `mcp__abfall__*` so they don't prompt. Add new allow entries here when adding tools that should run unattended (e.g. via `briefing-agent` or scheduled jobs). **Wird nicht ins Git-Repo eingecheckt** (Konvention: `.local.json`-Suffix → maschinen-spezifische Permission-Whitelist; `.gitignore` schließt es aus).
- **`settings.json`** — global settings (theme, `permissions.defaultMode: acceptEdits`).

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
