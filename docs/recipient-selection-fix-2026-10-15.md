# BHM Mailer — wybór i dodawanie odbiorców, 2026-10-15

Task: `BHM-RECIPIENTS-2026-10-15`. Lokalna delta; GitHub read-only, bez deploy i realnego SMTP. Jedyny rejestr wymagań: `PROJECT_BRIEF.md`, S01–S08.

## Diagnoza i granice dowodu

Root: `C:\Users\info\AGENTS\BHM Mailer`; branch `main`; HEAD `37ce3a788ba1cd01476a016c8113db52bccd45e9`; fetch/push remote `https://github.com/ProgresLab/BHM-mailer.git`. Zastano liczne zmiany niecommitowane, w tym nowe moduły, testy i narzędzia poprzedniej modernizacji. Zachowano je. Próba `git ls-remote` nie mogła połączyć się z GitHub przez skonfigurowane proxy; aktualnego zdalnego tipa nie potwierdzono ponownie.

Pierwsza próba na **niezmienionym aktualnym kodzie**, świeżym Chromium i nowej syntetycznej bazie 8018 **nie odtworzyła martwych checkboxów**: kliknięcie marcin dało licznik 1, poprawny POST i zapis; select-visible również działał, bez błędów JS. Dowód: `output/recipient-qa/reproduction.json`, `output/playwright/recipient-before.png`. Nie przypisujemy temu zgłoszeniu niepotwierdzonej awarii backendu.

Odczyt operacyjnego 8000 przed zmianą: HTTP 200, 500 aktywnych checkboxów, licznik 0, endpoint selection obecny w OpenAPI; serwowany JS był identyczny z lokalnym plikiem. URL JS nie zawierał wersji, odpowiedź miała ETag/Last-Modified. Nie wykonano POST na operacyjnej kampanii. Dowód: `operational-readonly.json`.

**Potwierdzony mechanizm odtwarzający objawy:** starszy JS z `HEAD` nasłuchuje `data-select-all` i `input[name=contact_ids]`, a aktualny szablon używa `data-visible-all` / `data-recipient`. Po podstawieniu tego starszego bundle w izolowanej przeglądarce ręczny checkbox nie zmienia licznika, a select-visible nie zaznacza wiersza. Test regresyjny rzeczywiście klika oba elementy i potwierdza te objawy. Screenshot: `recipient-legacy-js-reproduction.png`. To dowód niezgodności wersji; **nie dowód, że dokładnie taki cache był w przeglądarce użytkownika**. Jej pierwotny stan nie był dostępny, więc ostateczna przyczyna tamtego incydentu pozostaje niepotwierdzona.

Niezależnie potwierdzono wadę dotychczasowego workflow: checkbox wywoływał automatyczny zapis, a `target = (existing - visible) | eligible` zastępował selekcję na widocznej stronie. Nie było oddzielnego tymczasowego zaznaczenia, akcji Add ani pełnej listy w podsumowaniu. Zapis nieaktualnego widoku z drugiej zakładki mógł usuwać odbiorców zapisanych z pierwszej. Samo przestawienie etykiety przycisku tego nie rozwiązuje.

## Zmiana

- Checkbox i „Zaznacz widoczne” zmieniają tylko tymczasowy stan strony oraz licznik; maksymalnie 500 widocznych kwalifikujących się wierszy. Nie ma autosave ani niejawnego zaznaczania innych stron.
- „Dodaj do kampanii” wysyła jeden jawny POST. Dopiero poprawna odpowiedź aktualizuje licznik dodanych i oznaczenia „Dodano”. Zapis nie przenosi do podsumowania i nie tworzy kolejki.
- Backend wykonuje sumę istniejących i nowych aktywnych ID w tej samej tabeli `campaign_selection`, pod `BEGIN IMMEDIATE`. Limit 1000 jest sprawdzany w transakcji przed zapisami. Ponowne dodanie jest idempotentne; niezaznaczenie istniejącego kontaktu go nie usuwa.
- Osobny endpoint usuwa pojedynczą pozycję z selekcji. Clear usuwa tylko selekcję danej kampanii, wymaga dialogu i jawnego potwierdzenia w żądaniu. Nie usuwa kontaktów ani nie zmienia ich statusów.
- „Przejdź do podsumowania” wymaga co najmniej jednego dodanego aktywnego kontaktu. Podsumowanie czyta pełną zapisaną listę, pokazuje liczbę wszystkich i aktywnych, wykluczone statusy, nazwę, Subject, język, ETA i usuwanie oraz powrót do dodawania. Końcowy POST startu nadal wymaga osobnego potwierdzenia, fingerprintu, domyślnego dry-run i jawnej zgody SMTP.
- GET stanu z SQLite przy focus/pageshow/visibility oraz powiadomienie BroadcastChannel odświeżają zakładki. Kanał przenosi tylko sygnał odczytu, nie jest drugim źródłem selekcji. Backend pozostaje rozstrzygający przy równoczesnych zapisach.
- Wersja URL JS odcina poprzedni URL cache. Przed dopuszczeniem zmian frontend wymaga kontraktu `explicit_add_v1` z nowego API; błąd lub starszy proces pokazuje blokadę, bez pozornego sukcesu i zapisu przez stare API.
- Nie zmieniono schematu, edytora rich text, e-mail rendererów, banerów, SMTP/workera, monitora ani unsubscribe.

## Walidacja

**47 testów unittest PASS**, `compileall app` PASS, `node --check app/static/app.js` PASS. Pełny zestaw obejmuje wcześniejsze testy fake SMTP, interwału 20 s, przerw 3600/300, recovery, importu, renderingów i końcowego potwierdzania. Sześć nowych testów sprawdza add/idempotencję, atomowy limit przy dwóch pisarzach, potwierdzony Clear z izolacją kampanii, jednego marcin/reload/summary/remove, filtry i statusy oraz błędne requesty. Log: `output/recipient-qa/tests.log`.

**14 scenariuszy rzeczywistego Chromium PASS** (`tools/recipient_browser_qa.cjs`, `output/recipient-qa/browser.json`):

1. Starszy JS odtwarza martwy licznik/select-visible; aktualny URL assetu jest wersjonowany.
2. Starsze API 405 blokuje zaznaczanie/Add/Clear z czytelnym komunikatem.
3. Szukaj marcin → checkbox → tymczasowe 1, w SQLite nadal 0 → Add → zapisane 1 → reload → dokładnie jeden marcin w podsumowaniu.
4. Desktop 1440, mobile 390 i 360: selekcja/podsumowanie, brak poziomego overflow strony; screenshoty wizualnie sprawdzone.
5. Usunięcie jednego odbiorcy w podsumowaniu; kontakt pozostaje w bazie.
6. 500 wierszy na stronie, zaznacz/odznacz widoczne, blokada podsumowania pustej selekcji.
7. 500 + 500 przez rzeczywiste linki paginacji → 1000 w SQLite → reload → 1000 wierszy podsumowania.
8. Próba 1001 → HTTP 400, nadal 1000 zapisanych, zaznaczenie tymczasowe zachowane, bez sukcesu UI.
9. Anulowanie Clear zachowuje 1000; zatwierdzenie czyści wyłącznie listę kampanii.
10. 500 + 300 z następnej strony + wyszukanie i dodanie kolejnego → 801, także po reload.
11. Syntetyczny HTTP 503: licznik zapisanych pozostaje 0, zaznaczenie 1, komunikat o niepotwierdzonym zapisie.
12. Dwa natychmiastowe kliknięcia Add: jeden request, jeden odbiorca.
13. Dwie otwarte zakładki: łączny zapis bez zastępowania, synchronizacja z SQLite i trwałość po reload.
14. Unsubscribed/bounced/invalid: checkboxy zablokowane; bezpośredni request również ich nie dodaje.

QA 8018: osobna baza `output/recipient-qa/synthetic.sqlite3`, 1504 syntetyczne kontakty, jedna kampania QA (ID 32), SMTP wymuszone OFF. Finalnie pozostawiono jednego `marcin@example.test` do podglądu. **Zero email_sends, zero send_attempt_history, zero last_sent_at**, integralność ok, zero naruszeń FK. Nie uruchamiano kolejki ani dry-run przez przeglądarkę.

Screenshoty w `output/playwright/`:

- `recipient-single-desktop.png`, `recipient-summary-desktop.png`;
- `recipient-selection-390.png`, `recipient-selection-360.png`;
- `recipient-summary-390.png`, `recipient-summary-360.png`;
- `recipient-1000-desktop.png`, `recipient-legacy-js-reproduction.png`.

## Port 8000 i operacyjna SQLite

Listener **PID 15184** pozostał bez restartu, z tym samym root/command/env i `SMTP_ENABLED=false`. Nowy Python/backend **nie jest aktywny na 8000**. Szablony i JS są plikami współdzielonymi z procesem; nie oznacza to przeładowania route'ów. Końcowa odczytowa próba Chromium na 8000 (wszystkie nie-GET/HEAD zablokowane przed nawigacją) potwierdziła HTTP 200, 500/500 checkboxów zablokowanych, Add/Clear zablokowane oraz **zero żądań zapisu**. To oczekiwana blokada niezgodnej wersji, nie akceptacja workflow na 8000. Dowód: `output/recipient-qa/browser-8000-readonly.json`.

Plik operacyjny pozostał identyczny: SHA-256 `afcdbc416d627970d5bbe9feb8ff91899f0436c15ed2436ff9ba33e4014fcb2f`, rozmiar 39362560, niezmienione `mtime_ns`. Nie wykonano migracji, zmiany operacyjnej kampanii, kontaktu, statusu, .env ani recovery. Dowód: `before.json`, `final-audit.json`.

Odczyt operacyjnej bazy przez SQLite `mode=ro` i backup **wyłącznie do pamięci** pozwolił uruchomić prawdziwe init/recover na kopii. Init jest no-op. Restart w obecnym stanie przewiduje **3 zmienione wiersze campaign_execution i 3 nowe execution_events**, bez zmian innych tabel. Mechanizm recovery pozostawiono bez zmian.

Do aktywacji potrzebna jest osobna zgoda użytkownika, zgodnie z granicą tego zadania: świeży spójny backup SQLite i powiązanych assets, ponowny preflight kopii, dokładnie jeden restart 8000 z SMTP OFF obejmujący przewidywane zapisy recovery, następnie odczytowa kontrola nowego API i UI. Faktyczny test zapisu do operacyjnej kampanii pozostaje poza tym zakresem. Nie zakładamy zgody na dodatkowe restarty ani na realne SMTP.

## Pliki i closeout

Delta dotyczy: `app/selection.py`, `app/main.py`, `app/static/app.js`, `app/static/styles.css`, `app/templates/base.html`, `app/templates/campaign_recipients.html`, `app/templates/campaign_confirm.html`, `tests/test_campaigns.py`, `tools/recipient_qa_server.py`, `tools/recipient_browser_qa.cjs`, niniejszego raportu oraz `AGENTS.md`, `README.md`, `PROJECT_BRIEF.md`.

Context Pack przejrzany: odpowiedzialności selekcji, testów i granice aktywacji zapisane lokalnie. Jeden rejestr Requirements & Acceptance; dokładnie jeden datowany wpis tego zadania w Change Log. Gate: `output/recipient-qa/closeout-gate.json`. HEAD/branch/remotes/index pozostawione bez zmian; bez commit/push/deploy. Bieżącego remote tipa nie odświeżono z powodu błędu sieci. QA 8018 zatrzymano po walidacji; fixture i screenshoty zachowano, można je otworzyć ponownie powyższym launcherem. Procesów 8000 i wcześniejszego QA 8017 nie zatrzymywano.
