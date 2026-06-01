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

(leer)

---

## ✅ DONE — kürzlich erledigt

(vollständige Historie → [`BACKLOG-ARCHIVE.md`](BACKLOG-ARCHIVE.md))

- ✅ **2026-06-01** **N6 / Latenz-Track geschlossen** — Optimierung ausgereizt. Schlüssel-Erkenntnis: **User-wahrgenommene Latenz = Trigger → Push = ~23s** (Alexa spricht beim Push); die 10.4s „Cleanup" danach sind für die UX tote Zeit (nur für `_run_lock`/Overlap relevant). Restliche 95% sind Claude-Prozess-Overhead ohne einfachen Hebel — die UX-relevanten Kandidaten wären nur `model: haiku` (Generation 9.6s) bzw. `--bare` (Boot 12s), beide mit Qualitäts-/Risiko-Trade-off. Bewusst nicht weiterverfolgt.
- ✅ **2026-06-01** **B3** — `briefing-trigger`-Service auf neuen Code (Subagent-Pattern, Hebel 2+3) umgestellt. Restart hat gegriffen (PID 7760 → 82964, ExecStart sauber ohne `--agent`-Flag).
- ✅ **2026-06-01** **N5** — Hebel 3 gemessen (1 Live-Trigger): Phase 2 = 12.0s, Phase 3 = 1.5s, Phase 4 = 9.6s, Phase 6 = 10.4s, **Total 33.5s**. Δ vs. Hebel-2-only (32.6s) = +0.9s → **im Rauschen**, kein messbarer Gewinn. Hebel 3 bleibt drin (kürzerer Prompt, kostet nichts). Bestätigt: Tool-Calls = 4.5%, restliche 95% = Claude-Prozess-Overhead (Boot/Generation/Cleanup).
- ✅ **2026-05-07** **Git-Setup** — Repo `kevinoehme/claude` initialisiert mit SSH-Auth (ed25519), Whitelist-`.gitignore` (schützt vor Secret-Leaks), README mit Komponenten-Übersicht. 24 Files initial gepusht.
- ✅ **2026-05-07** **Latenz-Optimierung** — Profiling-Layer + 3 Hebel evaluiert. Hebel 2 (Multi-Push) deployed (~1.8s), Hebel 1 (`--agent`-Direkt-Subagent) verworfen (Wash), Hebel 3 (Prompt-Straffung) vorbereitet. Hauptengpass bleibt LLM-Latenz (87% der ~33s).
- ✅ **2026-05-07** **N4 / N3 / N2** — `Invalid API key`-Diagnose, `services/sync_anthropic_key.sh` geschrieben + ausgeführt, End-to-End-Trigger verifiziert (Alexa spricht).
