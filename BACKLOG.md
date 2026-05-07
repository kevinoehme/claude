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

### B3 — `briefing-trigger` neu starten
Code auf Disk ist aktuell (Subagent-Pattern, Hebel 2 + Hebel 3 drin), aber Service läuft noch mit alter In-Memory-Variante (PID 7760, `--agent`-Flag aktiv) — letzter Restart-Versuch hat nicht gegriffen.

```bash
sudo systemctl restart briefing-trigger && sleep 1 && systemctl show -p MainPID,ActiveEnterTimestamp --value briefing-trigger
```

Erfolg = neue PID ≠ 7760 UND Timestamp ≠ 21:41:02. Solange offen: Service funktioniert, ist nur ungewollt im Hebel-1-Mix-Modus.

### O6 — `mcp/gmx_mail.py` chown auf `claude:claude`
Aktuell `root:root` (alle anderen MCP-Files sind `claude:claude`), vermutlich Restartefakt aus früherem privilegiertem Editor-Run.

```bash
sudo chown claude:claude /home/claude/mcp/gmx_mail.py
```

---

## 🟡 NEXT — sobald B3 durch ist

### N5 — Hebel 3 sauber messen
Nach erfolgreichem B3-Restart einmal triggern, `profile.log` auswerten. Erwartet: Phase 2 ~9–10s (vorher 10.3s, leicht weniger durch −9% Prompt-Länge), Phase 4 ~7–9s, Phase 6 ~9s, Total ~28–32s. Wenn Δ vs. Hebel-2-only (32.6s) < 2s → Hebel 3 ist im Rauschen, kann bleiben oder rückgängig gemacht werden.

---

## ⚪ OPEN — eingeplant

### N6 — Weitere Latenz-Hebel (low-prio, optional)
- **Modell-Wechsel** briefing-agent: `sonnet` → `haiku` im Frontmatter `model:`-Zeile. Erwartet 5–10s schneller in Phase 4, aber Tonfall-Qualität testen.
- **`--bare`-Modus** für `claude -p` mit expliziter MCP-Konfig — skippt CLAUDE.md-Auto-Discovery + hooks. Riskant (MCP-Konfig muss inline bereitgestellt werden), potenziell 5–10s.
- **`--effort low`**: Anthropic-Reasoning-Tokens reduzieren. Schmaler Patch, ungewisser Gewinn.

---

## ✅ DONE — kürzlich erledigt

(vollständige Historie → [`BACKLOG-ARCHIVE.md`](BACKLOG-ARCHIVE.md))

- ✅ **2026-05-07** **Git-Setup** — Repo `kevinoehme/claude` initialisiert mit SSH-Auth (ed25519), Whitelist-`.gitignore` (schützt vor Secret-Leaks), README mit Komponenten-Übersicht. 24 Files initial gepusht.
- ✅ **2026-05-07** **Latenz-Optimierung** — Profiling-Layer + 3 Hebel evaluiert. Hebel 2 (Multi-Push) deployed (~1.8s), Hebel 1 (`--agent`-Direkt-Subagent) verworfen (Wash), Hebel 3 (Prompt-Straffung) vorbereitet. Hauptengpass bleibt LLM-Latenz (87% der ~33s).
- ✅ **2026-05-07** **N4 / N3 / N2** — `Invalid API key`-Diagnose, `services/sync_anthropic_key.sh` geschrieben + ausgeführt, End-to-End-Trigger verifiziert (Alexa spricht).
