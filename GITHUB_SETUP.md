# GitHub Setup: DSIX Security Index

## 1. Repository erstellen

```bash
# Auf GitHub.com:
# → New repository
# → Name: dsix-tool (oder wie du willst)
# → Description: "Automated Germany security index from RSS feeds"
# → Public (für Portfolio) oder Private (für Test)
# → Add .gitignore: Python
# → Add README.md
# → Create repository

# Lokal:
git clone https://github.com/<dein-username>/dsix-tool.git
cd dsix-tool
```

## 2. Projekt-Dateien pushen

```bash
# Entpack die ZIP hier rein
unzip dsix-tool.zip -d .

# Überprüfe, dass .gitignore die richtigen Dateien ausschließt:
cat .gitignore
# sollte enthalten: __pycache__/, *.pyc, .env

# Commit
git add .
git commit -m "Initial commit: DSIX pipeline with Groq provider"
git push
```

## 3. GitHub Secrets konfigurieren (API Key verstecken)

**Die kritische Part:** Dein `GROQ_API_KEY` darf **nie** ins Repo gehen.

```bash
# Auf GitHub.com:
# → Settings → Secrets and variables → Actions
# → "New repository secret"
#   Name: GROQ_API_KEY
#   Value: <dein-groq-api-key-von-console.groq.com>
# → Add secret

# Optional: weitere Secrets (falls du später wechselst)
# GOOGLE_API_KEY (für Gemini fallback)
# ANTHROPIC_API_KEY (falls nötig)
```

**Wichtig:** Diese Secrets sind:
- ✅ Automatisch maskiert in Workflow-Logs (GitHub zeigt `***` statt des Keys)
- ✅ Nur im Workflow-Kontext sichtbar (nicht im Repo-Code)
- ✅ Verschlüsselt gespeichert bei GitHub
- ✅ Nur du + GitHub Actions können sie auslesen

## 4. GitHub Pages aktivieren (Dashboard hosting)

```
Auf GitHub.com:
→ Settings → Pages
→ Build and deployment
  - Source: Deploy from a branch
  - Branch: main (oder main, je nachdem)
  - Folder: /docs
→ Save

→ Nach ~1min ist dein Dashboard unter:
   https://<dein-username>.github.io/dsix-tool/
```

## 5. Workflow zum ersten Mal manuell triggern

```
→ Actions Tab
→ "Update security index" (der Workflow aus .github/workflows/update.yml)
→ "Run workflow" Button (oben rechts)
→ Refresh nach 1-2 Minuten

Logs sollten zeigen:
  ✓ Fetched 37 items, X new
  ✓ X/37 items passed Stage 1 filter
  ✓ X confirmed incidents extracted
  ✓ DSIX score: 100 (Stable)
  ✓ Commit updated data [skip ci]
```

Wenn es grün wird: **Glückwunsch, das Ding läuft!**

## 6. Konfigurieren (Optional)

Default-Aufteilung: **Groq** filtert (Stage 1, `FILTER_BACKEND`), **Gemini**
extrahiert präzise (Stage 2, `LLM_PROVIDER`). Beide Secrets (`GROQ_API_KEY`
und `GOOGLE_API_KEY`) solltest du daher hinterlegen. Zum Ändern:

```
→ Settings → Secrets and variables → Variables
→ "New repository variable"
   Name: LLM_PROVIDER      Value: groq (oder anthropic, openai, etc.)
   Name: FILTER_BACKEND    Value: keyword (oder smollm)
```

Einmalig vor dem ersten geplanten Lauf lohnt sich außerdem der manuelle
Workflow **"Seed backlog (cold start)"** unter dem Actions-Tab — der füllt
das Dashboard rückwirkend mit den letzten ~60 Tagen, statt bei Null zu
starten.

---

## Sicherheit: API Key verstecken

**Was gehört NICHT ins Repo:**
```
❌ GROQ_API_KEY=sk-...   (niemals hart-coded)
❌ .env file (schon in .gitignore, aber doppelt checken)
❌ API Keys in README/Docs/Code
```

**Was du stattdessen tust:**
```
✅ .env.example (mit placeholder, kein echter Key)
✅ GROQ_API_KEY als GitHub Secret (verschlüsselt)
✅ .github/workflows/update.yml liest Secret via ${{ secrets.GROQ_API_KEY }}
```

**Workflow-Datei (sicher):**
```yaml
- name: Run pipeline
  env:
    GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
  run: python -m src.pipeline
```

GitHub ersetzt `${{ secrets.GROQ_API_KEY }}` zur Laufzeit mit dem echten Key,
aber in den Logs wird er automatisch maskiert (= `***`).

---

## Verification Checklist

Nach dem Setup sollte das hier stimmen:

```
✅ repo/config/feeds.json              (37 feeds)
✅ repo/src/pipeline.py                (main orchestration)
✅ repo/docs/index.html                (dashboard)
✅ repo/.github/workflows/update.yml   (scheduled crawl)
✅ repo/.gitignore                     (has __pycache__, .env, *.pyc)
✅ GitHub Secret: GROQ_API_KEY         (verschlüsselt gespeichert)
✅ GitHub Pages: /docs deployed        (live unter dein-username.github.io/dsix-tool/)
✅ Workflow: manuell getestet + grün   (logs zeigen "DSIX score: X")
```

Wenn alle ✅, bist du ready für den auto-Cron (alle 6h).

---

## Troubleshooting

**Workflow schlägt fehl:**
- Check Logs: Actions → Workflow → Latest run → Logs
- Häufige Fehler:
  - `GROQ_API_KEY not set` → Secret ist falsch geschrieben oder nicht hinzugefügt
  - `Feed parsing failed` → Eine Feed-URL ist dead, entfern sie aus feeds.json
  - `LLM extraction failed` → API Key ungültig oder Groq API ist down

**Pages zeigt 404:**
- Check: Settings → Pages → Branch ist `main`, Folder ist `/docs`
- Wait 2-3 min nach dem Commit
- Hard refresh browser (Ctrl+Shift+R)

**Workflow pusht keine Commits zurück:**
- Check: repo/.github/workflows/update.yml, Zeile `git push`
- Stelle sicher, dass die GitHub Action **write** permissions hat:
  - Settings → Actions → General → Workflow permissions
  - Sollte sein: "Read and write permissions"
