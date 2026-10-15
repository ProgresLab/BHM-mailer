# Blokada odbiorców na 8000 — 2026-10-16

Task `BHM-RECIPIENT-RUNTIME-2026-10-16`. Status: **BLOCKED / requires authorized activation**, bez odbioru operacyjnego PASS. Jedyny rejestr wymagań: `PROJECT_BRIEF.md`, D01–D06.

## Potwierdzona przyczyna

Root `C:\Users\info\AGENTS\BHM Mailer`, branch `main`, HEAD `37ce3a788ba1cd01476a016c8113db52bccd45e9`, fetch/push `https://github.com/ProgresLab/BHM-mailer.git`. Zastane liczne zmiany lokalne zachowano; indeks pusty. Nie wykonywano Git write ani deploy.

Listener 127.0.0.1:8000: **PID 15184**, start `2026-10-15T21:06:00.4995690Z`. Odczyt procesu potwierdził cwd tego projektu, komendę `.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`, interpreter bazowy `C:\Python314\python.exe`, operacyjną bazę `data/bhm_mailer.sqlite3`, assets `uploads/campaign_assets` i **SMTP_ENABLED=false**. Inspektor zwraca tylko te dozwolone zmienne; nie drukuje sekretów.

Rzeczywista przeglądarka otwiera `/campaigns/32/recipients` (200), po czym wysyła:

```text
GET http://127.0.0.1:8000/campaigns/32/selection
HTTP 405 Method Not Allowed
Allow: POST
{"detail":"Method Not Allowed"}
```

Log tego procesu (`output/evidence/http500-8000-final-stdout.log`) z bieżącej próby:

```text
INFO:     127.0.0.1:59354 - "GET /campaigns/32/selection HTTP/1.1" 405 Method Not Allowed
```

OpenAPI z 8000 udostępnia wyłącznie POST na tej ścieżce. Aktualny `app/main.py` ma już GET (`campaign_selection_state`) i kontrakt `workflow=explicit_add_v1`, `selected_ids`, liczniki i `editable`. Plik main.py zmieniono `2026-10-15T21:24:51Z`, po starcie procesu. Dokładnego hasha kodu w pamięci Python nie deklarujemy; wersję backendu identyfikuje starszy zestaw tras zwracany przez działający proces. Reload jest wyłączony.

Serwowany `app.js?v=recipients-20261015-1` jest hash-identyczny z lokalnym JS. Brak błędów JavaScript i błędów transportu. W `initSelection → refresh` GET otrzymuje 405; catch ustawia `ready=false`, `editable=false` i komunikat blokady. `apply` dodatkowo wymaga zgodnego kontraktu. Wszystkie 500 checkboxów i Add są disabled. To **starszy backend z nowymi plikami UI**, nie awaria SQLite ani martwe listenery JS.

## Zakres naprawy

Kanoniczny GET/Add jest już poprawny i działa na świeżym procesie QA. Nie zmieniano aplikacji, UI ani blokady bezpieczeństwa; nie dodawano fallbacków. Usunięcie przyczyny wymaga załadowania istniejącego źródła przez kontrolowany restart 8000, podlegający zgodzie na zapisy operacyjne.

- `tools/recipient_runtime_probe.cjs`: browser probe 8000, blokuje inne originy i metody poza GET/HEAD; zapisuje bezpieczny fragment API, OpenAPI, porównanie JS i screenshot z zamaskowanymi danymi.
- `tools/recipient_activation_preflight.py`: SQLite `mode=ro`, backup tylko do RAM, prawdziwe init/recover wyłącznie na kopii; raportuje zmienione kolumny i hashe plików. Nie uruchamia workera ani serwera.
- `tools/recipient_browser_qa.cjs`: dodano niezależny od API odczyt SQLite przed/po Add, po reload oraz po 500 i 1000.

## Walidacja

47 unittest OK w 42.608 s, `compileall app` i preflight oraz składnia trzech JS OK. Fake SMTP obejmuje 1000 prób, odstęp minimum 20 s i przerwy 3600/300. Zero realnego SMTP.

14 scenariuszy Chromium na izolowanej 8018 OK, bez błędów JS. Pełna ścieżka: wyszukaj `marcin` → zaznacz → tymczasowe 1, SQLite nadal 0 → Add HTTP 200 → SQLite dokładnie `marcin@example.test` → reload, licznik 1/1000 → podsumowanie dokładnie 1. Osobno 500 → SQLite 500 → link strony 2 → dodaj 500 → SQLite 1000 → reload 1000 → podsumowanie 1000. Sprawdzono limit 1001, błędy API, clear/remove, dwie zakładki, podwójny klik, statusy wykluczone i mobile 390/360. Nie rozpoczęto kolejki.

Dowody:

- `output/recipient-runtime/8000-browser.json`, `process.json`, `activation-preflight.json`, `tests.log`, `closeout.json`;
- `output/recipient-qa/browser.json` zawiera `sqliteChecks`;
- `output/recipient-runtime/8000-recipient-gate.png` — faktyczna blokada 8000, prywatne treści zamaskowane;
- `output/playwright/recipient-single-desktop.png`, `recipient-summary-desktop.png`, `recipient-1000-desktop.png`, `recipient-summary-360.png` — QA. Wizualnie sprawdzono blokadę 8000, pojedynczy kontakt i mobile summary.

## Dokładny krok aktywacji wymagający zgody

Preflight: kampania 32 `approved`; brak `sending` w email_sends/send_attempt_history i brak powiadomień w toku. Kampanie 17/18/28 mają już `state=interrupted`, `mode=smtp`, `manual_pause=1`. Init no-op; integrity `ok`, FK 0. Restart przewiduje wyłącznie:

1. `campaign_execution.updated`: trzy istniejące wiersze, campaign_id 17, 18, 28.
2. `execution_events`: trzy dopisane zdarzenia restartu dla tych kampanii.

Zgoda powinna obejmować świeży spójny backup SQLite i wszystkich `uploads/campaign_assets`, ponowny preflight kopii, dokładnie jeden kontrolowany restart PID 15184 z tymi zapisami recovery i jawnym SMTP OFF, następnie GET API, kontrolę UI 8000 i porównanie wszystkich tabel/assets z backupem. Jeśli preflight wykaże inny zakres, zatrzymać aktywację przed startem. Bez automatycznego wznowienia kolejek. Nie używać zwykłego `start.bat`, który nie gwarantuje procesowego override SMTP OFF.

Po aktywacji można zaznaczyć i odznaczyć checkbox bez zapisu oraz sprawdzić odblokowanie Add. Add do kampanii operacyjnej jest oddzielnym zapisem wymagającym zgody na konkretny kontakt; tu zapisy testowano na syntetycznej SQLite. Backup na dysku i restart nie zostały wykonane.

## Context Pack Closeout

AGENTS.md przejrzano: odpowiedzialności i bramki pozostają właściwe, bez zmiany. README i PROJECT_BRIEF uzupełniono o potwierdzoną diagnozę, narzędzia i zakres aktywacji. D01–D06 w jednym rejestrze; dokładnie jeden wpis Change Log tego zadania. Poprzednie wpisy zachowano. QA 8018 zatrzymano po testach; operacyjnego procesu nie restartowano. Bez operacyjnych zmian kontaktów, selekcji, historii, unsubscribe, `.env`, commit/push/deploy.
