# Backlog — /home/claude

Persistente Aufgabenliste. Wird vom User & von Claude gemeinsam gepflegt.
**Konvention:**
- `🔴 BLOCKED` → wartet auf User-Aktion (sudo, externe Konfig, Entscheidung)
- `🟡 NEXT` → unmittelbar als nächstes dran
- `🟢 DOING` → aktuell in Arbeit
- `⚪ OPEN` → eingeplant, noch nicht aktiv
- `✅ DONE` → erledigt, bleibt zur Historie kurz stehen, dann ins Archiv (`BACKLOG-ARCHIVE.md`)

Claude liest diese Datei bei jedem Sessionstart (zusammen mit `architecture.drawio`).

---

## 🔴 BLOCKED — wartet auf dich

### B3 — `briefing-trigger` neu starten, damit Hebel-1-Rollback greift
- Code auf Disk ist aktuell (Subagent-Pattern, Hebel 2 + Hebel 3 drin), aber Service läuft seit 21:41:02 UTC mit alter In-Memory-Variante (PID 7760, `--agent`-Flag aktiv) — letzter Restart-Versuch hat nicht gegriffen.
- Aufruf **im Host-Terminal** (mit Verifikation):
  ```bash
  sudo systemctl restart briefing-trigger && sleep 1 && systemctl show -p MainPID,ActiveEnterTimestamp --value briefing-trigger
  ```
- Erfolg = neue PID ≠ 7760 UND Timestamp ≠ 21:41:02. Nach Restart läuft Subagent-Pattern + Multi-Push + gestraffter Prompt (~30s erwartet, vs. Hebel-1-Mix ~31-37s aktuell).
- Solange B3 offen: Service funktioniert, ist nur ungewollt im Hebel-1-Mix-Modus.

### O6 — `mcp/gmx_mail.py` chown auf `claude:claude`
- Aktuell `root:root` (alle anderen MCP-Files sind `claude:claude`)
- Vermutlich Restartefakt aus früherem privilegiertem Editor-Run
- Aufruf **im Host-Terminal**: `sudo chown claude:claude /home/claude/mcp/gmx_mail.py`

---

## 🟡 NEXT — sobald B3 durch ist

### N5 — Hebel 3 sauber messen (Subagent-Pattern + gestraffter Prompt)
Nach erfolgreichem B3-Restart einmal triggern, profile.log auswerten. Erwartet: Phase 2 ~9–10s (vorher 10.3s, leicht weniger durch −9% Prompt-Länge), Phase 4 ~7–9s, Phase 6 ~9s, Total ~28–32s. Wenn Δ vs. Hebel-2-only (32.6s) < 2s → Hebel 3 ist im Rauschen, kann bleiben oder rückgängig gemacht werden.

### N6 — Optional: weitere Latenz-Hebel
- **Modell-Wechsel briefing-agent: sonnet → haiku** (im Frontmatter `model:`-Zeile). Erwartet 5–10s schneller in Phase 4, aber Tonfall-Qualität testen.
- **`--bare`-Modus** für `claude -p` mit expliziter MCP-Konfig — skippt CLAUDE.md-Auto-Discovery + hooks. Riskant (MCP-Konfig muss inline bereitgestellt werden), potenziell 5–10s.
- **`--effort low`**: Anthropic-Reasoning-Tokens reduzieren. Schmaler Patch, ungewisser Gewinn.

---

## ⚪ OPEN — eingeplant

*(aktuell leer — alles aktive ist BLOCKED oder NEXT)*

---

## ✅ DONE — kürzlich erledigt

(ältere Einträge → `BACKLOG-ARCHIVE.md`)

- ✅ **2026-05-07** **O7** — `BACKLOG-ARCHIVE.md` angelegt, ältere DONE-Items dorthin ausgelagert. `BACKLOG.md` zeigt nur noch jüngste Historie.
- ✅ **2026-05-07** **O5** — `mcp/cron_record.py` als aktiv produktiv identifiziert (User-Crontab `5 * * * *`, schreibt sauber). In CLAUDE.md unter neuer Sektion „Cron-Hilfsskript" dokumentiert; Architektur-Diagramm um Container „System Cron" + Box `cron_record.py` + Edges → openmeteo / sqlite erweitert.
- ✅ **2026-05-07** **B2** — `briefing-trigger`-Service neu gestartet (PID 5473 → 6315, 19:41:40 UTC). Logging-Patch aktiv.
- ✅ **2026-05-07** **N2** — Diagnose: 39-Byte-stdout = `Invalid API key · Fix external API key`. Ursache via `/proc/<PID>/environ`-Inspektion + API-Probe isoliert: Service-Env-Key war 103-char-Key mit HTTP 401, divergent zum 108-char-Key in `~/.bashrc`. Fix → N3.
- ✅ **2026-05-07** **N3** — `services/sync_anthropic_key.sh` geschrieben (idempotent, atomar, kein Key-Echo) und ausgeführt. Service läuft jetzt mit dem `~/.bashrc`-Key (PID 6726, API-Probe HTTP 200). Skript-Bug (Hash-Inkonsistenz `printf` vs `awk\|sha256sum` durch trailing-newline) im selben Turn gefixt — `hash16()`-Helper sorgt für konsistente no-newline-Hashes überall.
- ✅ **2026-05-07** **N4** — End-to-End-Trigger nach Sync-Fix verifiziert (PID 6726, mehrfach `rc=0`, Alexa spricht). Bei der Gelegenheit Latenz gemessen: ~30–38s pro Lauf (Mittel ~34s).
- ✅ **2026-05-07** **Latenz-Profiling** — `mcp/profiling.py` (atomares Append-Logging via `os.write`) + `@profile`-Decorator auf alle Tools von `weather`, `abfall`, `mail_check`, `mqtt_notify` + `module_load`-Marker beim Server-Start. Profile-Log unter `/home/claude/data/profile.log`. Aufschlüsselung: ~7% Cold-Start, ~29% Boot bis 1. Tool, ~5% eigentliche Tool-Calls, ~22% Briefing-Generation, ~10% Mehrfach-Push-Lücken, ~27% Cleanup. **Tool-Calls sind nicht der Engpass** — 87% sind LLM-Zeit.
- ✅ **2026-05-07** **Hebel 2** — `mqtt_notify.send_notifications_multi` (1 TCP-Connect für N Topics, `paho.publish.multiple`) + briefing-agent-Prompt auf 1 Push-Aufruf statt 2 angepasst. Strukturell sichtbar (1 Tool-Call statt 2), gemessener Netto-Gewinn ~1.8s in Phase 4+5, im Rauschen der Sonnet-Variance.
- ✅ **2026-05-07** **Hebel 1 verworfen** — `claude -p --agent briefing-agent` testet Direkt-Subagent (Hauptmodell-Wrapper umgehen). Strukturell ~13s gespart in Phase 2+6, aber +12s in Phase 4 (Sonnet als Top-Level langsamer als als Subagent — Hauptmodell wärmt offenbar Tool-Schema-Cache vor). Netto Wash → zurückgerollt zur Subagent-Variante.
- ✅ **2026-05-07** **Hebel 3 (vorbereitet)** — briefing-agent-Prompt von 111 → 101 Zeilen gestrafft (Verbotene-Muster-Liste komprimiert, Beispiele 3→2). Sauber-Messung steht aus → siehe N5.
