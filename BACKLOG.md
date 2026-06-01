# Backlog — /home/claude

Persistente Aufgabenliste. Wird vom User & von Claude gemeinsam gepflegt.
**Konvention:**
- `🔴 BLOCKED` → wartet auf User-Aktion (sudo, externe Konfig, Entscheidung)
- `🟡 NEXT` → unmittelbar als nächstes dran
- `🟢 DOING` → aktuell in Arbeit
- `⚪ OPEN` → eingeplant, noch nicht aktiv
- `✅ DONE` → erledigt, bleibt zur Historie kurz stehen, dann ins Archiv (`BACKLOG-ARCHIVE.md`)

Claude liest diese Datei bei jedem Sessionstart. (`architecture.drawio` nur on-demand bei strukturellen Architektur-Änderungen — siehe `CLAUDE-workflow.md`.)

---

## 🔴 BLOCKED — wartet auf dich

### O6 — `mcp/gmx_mail.py` chown auf `claude:claude`
Aktuell `root:root` (alle anderen MCP-Files sind `claude:claude`), vermutlich Restartefakt aus früherem privilegiertem Editor-Run.

```bash
sudo chown claude:claude /home/claude/mcp/gmx_mail.py
```

---

## 🟡 NEXT

(leer — N5 gemessen, siehe DONE. Nächster optionaler Schritt: N6.)

---

## ⚪ OPEN — eingeplant

### N6 — Weitere Latenz-Hebel (low-prio, optional)
- **Modell-Wechsel** briefing-agent: `sonnet` → `haiku` im Frontmatter `model:`-Zeile. Erwartet 5–10s schneller in Phase 4, aber Tonfall-Qualität testen.
- **`--bare`-Modus** für `claude -p` mit expliziter MCP-Konfig — skippt CLAUDE.md-Auto-Discovery + hooks. Riskant (MCP-Konfig muss inline bereitgestellt werden), potenziell 5–10s.
- **`--effort low`**: Anthropic-Reasoning-Tokens reduzieren. Schmaler Patch, ungewisser Gewinn.

---

## ✅ DONE — kürzlich erledigt

(vollständige Historie → [`BACKLOG-ARCHIVE.md`](BACKLOG-ARCHIVE.md))

- ✅ **2026-06-01** **B3** — `briefing-trigger`-Service auf neuen Code (Subagent-Pattern, Hebel 2+3) umgestellt. Restart hat gegriffen (PID 7760 → 82964, ExecStart sauber ohne `--agent`-Flag).
- ✅ **2026-06-01** **N5** — Hebel 3 gemessen (1 Live-Trigger): Phase 2 = 12.0s, Phase 3 = 1.5s, Phase 4 = 9.6s, Phase 6 = 10.4s, **Total 33.5s**. Δ vs. Hebel-2-only (32.6s) = +0.9s → **im Rauschen**, kein messbarer Gewinn. Hebel 3 bleibt drin (kürzerer Prompt, kostet nichts). Bestätigt: Tool-Calls = 4.5%, restliche 95% = Claude-Prozess-Overhead (Boot/Generation/Cleanup).
- ✅ **2026-05-07** **Git-Setup** — Repo `kevinoehme/claude` initialisiert mit SSH-Auth (ed25519), Whitelist-`.gitignore` (schützt vor Secret-Leaks), README mit Komponenten-Übersicht. 24 Files initial gepusht.
- ✅ **2026-05-07** **Latenz-Optimierung** — Profiling-Layer + 3 Hebel evaluiert. Hebel 2 (Multi-Push) deployed (~1.8s), Hebel 1 (`--agent`-Direkt-Subagent) verworfen (Wash), Hebel 3 (Prompt-Straffung) vorbereitet. Hauptengpass bleibt LLM-Latenz (87% der ~33s).
- ✅ **2026-05-07** **N4 / N3 / N2** — `Invalid API key`-Diagnose, `services/sync_anthropic_key.sh` geschrieben + ausgeführt, End-to-End-Trigger verifiziert (Alexa spricht).
