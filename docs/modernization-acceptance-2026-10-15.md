# BHM Mailer — lokalna modernizacja 2026-10-15

Wynik: implementacja lokalna zakończona i zweryfikowana na danych syntetycznych. Nie jest to akceptacja realnego SMTP, operacyjnej migracji ani Outlooka. Jedyny rejestr wymagań znajduje się w `PROJECT_BRIEF.md → Requirements & Acceptance`.

## Tożsamość i granice

- Root: `C:\Users\info\AGENTS\BHM Mailer`.
- Fetch/push: `https://github.com/ProgresLab/BHM-mailer.git`; branch `main`.
- HEAD i świeży tip main przed zapisami: `37ce3a788ba1cd01476a016c8113db52bccd45e9`; start z czystego drzewa.
- Lokalnie zmieniono źródła i context pack. Bez commit/push, deployu i zapisów zewnętrznych.
- Istniejący proces na `127.0.0.1:8000` pozostał uruchomiony; nie restartowano go ani nie aktywowano nowego kodu na jego bazie.
- Testy: losowe katalogi `output/test-runtime/`; visual QA: `output/qa/synthetic.sqlite3` oraz `output/qa/assets/`, port 8017, SMTP wymuszone na false.
- Operacyjna baza nie była migrowana ani używana do testów. PowerShell nie mógł odczytać jej hasha z powodu otwartego uchwytu; nie deklarujemy porównania SHA-256. Odczyt metadanych pokazał modyfikację sprzed prac; metadane nie zastępują dowodu integralności.

## Co działa

FastAPI/Jinja2/SQLite i lokalne uruchamianie zachowano. Dodano kontrolowany rich text, edycję draftu, osobną nazwę/Subject/nagłówek, PL/EN, opcjonalny CTA i baner z prywatnym CID. Zatwierdzone treści i snapshoty są zablokowane dla edycji.

Selekcja jest kanonicznie zapisana w SQLite, stronicowana po 500, ograniczona do 1000 i niezależna od filtrów/odświeżenia. Serwer ponownie sprawdza statusy, a worker sprawdza je jeszcze raz bezpośrednio przed próbą.

Worker działa w jednym wątku pod blokadą procesu OS i rezerwacją SQLite. Nie trzyma połączenia SQLite podczas SMTP ani oczekiwania. Ręczna pauza nie przerywa nieodwracalnie trwającej próby; wynik jest zapisywany przed zatrzymaniem kolejki. Crash/timeout nie powoduje automatycznego ponowienia. Nowy dziennik zachowuje wyniki poszczególnych prób także po ponowieniu definitywnie odrzuconego 4xx. Zmiana tożsamości SMTP blokuje wznowienie.

Powiadomienia administracyjne o wypisie zachowano jako trwałą kolejkę obsługiwaną przez tego samego workera po zakończeniu kampanii. Zewnętrzny endpoint, format podpisu HMAC i konfiguracja sekretu nie zostały zmienione. Dry-run nie ustawia `last_sent_at`, `sent_at` ani `accepted_at`.

Osobny monitor odświeża się co 2,5 s, ma liczniki, bieżący/następny adres, czasy, przybliżone ETA, pauzę/wznowienie i osiem zdarzeń. Pełna lista odbiorców jest na osobnej stronie historii. Historia kontaktu, eksport CSV, import Trace oraz import XLSX pozostają dostępne. Naprawiono domykanie skoroszytu XLSX wykryte przez regresję.

## Dowody automatyczne

`python -m compileall app` i `.venv/Scripts/python.exe -m unittest discover -s tests -v`: **40 testów OK**. Log: `output/evidence/tests.log`.

Symulacja 1000 real-mode prób wyłącznie przez fake SMTP i zegar testowy:

- 1000 akceptacji fake SMTP, żadnego połączenia z kontem/domeną klienta.
- Minimalny odstęp startów: **20,0 s**. Dla wolnego SMTP sprawdzono odstęp start→start **35 s**, bez dodatkowego opóźnienia 20 s po zakończeniu.
- Początki przerw względem startu: **3600, 7500, 11400, 15300, 19200 s**.
- Każda przerwa trwała **300 s**. Różnica 3900 s między początkami to 3600 s aktywnej pracy + 300 s przerwy.
- Maksymalny odstęp sąsiednich startów: 320 s (20 s zwykłego odstępu + 300 s przerwy).
- Każdy odbiorca miał jedną próbę; brak ponowienia zaakceptowanych rekordów. Końcowa obserwacja stanu completed nastąpiła przy 21500 s zegara testowego, próbkowanego co 20 s; nie jest to czas ścienny rzeczywistej wysyłki.

Dalsze testy obejmują selekcję 5676, 500+500 i limit, wykluczenia, brak duplikatów, restart pomiędzy próbami i w trakcie niepewnej próby, przerwę trwającą przez restart, pauzę podczas SMTP/automatycznej przerwy, 4xx/cooldown i 550, dwa uruchomienia/two blokady procesu, zmianę tożsamości SMTP, HMAC/unsubscribe, Trace/eksport, MIME/CID i sanitizację HTML/URL. Trasy statusu i kontaktów odpowiadają podczas zablokowanego fake SMTP przy kolejce 1000; równoległy writer może zatwierdzić transakcję podczas wywołania sendera.

Migracja: fixture schematu z baseline Git, syntetyczne stare rekordy, backup SQLite, dwukrotne uruchomienie migracji, identyczność istniejących pól i snapshotów, `integrity_check=ok`, pusty `foreign_key_check`. Backup testowy nie zmienił hasha. To nie zastępuje preflightu kopii aktualnej bazy operacyjnej.

## Visual QA i marka

Oficjalną [stronę BHM](https://bhm-chemicals.com/) otwarto w działającej przeglądarce. Potwierdzono canonical root, Aptos/Segoe UI z fallbackami, granat nagłówków RGB(17,38,58), biel/szarości, powściągliwe przyciski i odstępy. E-mail adaptuje ten charakter do tabel 600 px i inline CSS; zielony jest akcentem list i linków, CTA jest granatowe. Wykorzystano wyłącznie oryginalne logo repozytorium. Baner w QA jest jawnie syntetyczny.

Potwierdzono działanie [PL produktów](https://bhm-chemicals.com/pl/produkty/) i [EN produktów](https://bhm-chemicals.com/en/products/); działający EN URL ma canonical `/EN/products/`. Adres firmy, NIP, REGON i KRS zgadzają się z oficjalną stroną [Terms & Conditions](https://bhm-chemicals.com/EN/terms-and-conditions/) oraz istniejącym rendererem. Zachowano `info@bhm-chemicals.com`.

Rzeczywiście wykonano w Chromium:

- Edycję, polskie znaki, pogrubienie, cofanie/ponawianie, wstawienie linku, zapis i ponowne otwarcie.
- Wklejenie HTML z formatowaniem: bold, italic, link i 22 px zachowane; script, event handler i obcy kolor usunięte.
- Checklistę utworzoną w świeżym drafcie, cofniętą, ponowioną i zapisaną. Visual QA wykryła i pozwoliła naprawić wcześniejszy przypadek graniczny z listą na końcu akapitu. Historia jest ograniczona do 100 stanów; treść nie jest przepisywana na input.
- Upload w rzeczywistym formularzu: podgląd blob przed zapisem miał 1200×400, następnie zapisany asset oraz logo poprawnie załadowały się w iframe.
- Podgląd z banerem, bez banera i z zablokowanymi obrazami. Baner 1200 px i logo miały poprawnie załadowane obrazy. Wewnętrzny e-mail przy szerokości 360 px miał `clientWidth=scrollWidth=360`.
- Zaznaczenie 500 + 500, odświeżenie z licznikiem 1000 i 500 zaznaczonymi na stronie 2, odrzucone zaznaczenie strony 3.
- Monitor kolejki 1000, rzeczywiste kliknięcia wznowienia/pauzy, zachowanie pauzy po odświeżeniu, odliczanie auto break 05:00 → 04:53 i ręczną pauzę podczas tej przerwy. Próg godziny przygotowano na syntetycznej bazie; nie czekano realnej godziny.
- Układ desktop, 390 px i 360 px. Główny monitor nie ma tabeli odbiorców. W QA `last_sent_at` pozostał pusty dla wszystkich kontaktów.

Zrzuty są rzeczywistymi przechwyceniami przeglądarki w `output/playwright/`:

- `editor-initial.jpg`, `editor-mobile.jpg`
- `preview-banner-desktop.jpg`, `preview-banner-mobile.jpg`, `preview-email-360.jpg`
- `preview-logo-desktop.jpg`, `preview-logo-mobile.jpg`, `preview-images-blocked.jpg`
- `recipients-desktop.jpg`, `recipients-mobile.jpg`
- `monitor-desktop.jpg`, `monitor-mobile.jpg`, `monitor-mobile-360.jpg`
- `monitor-auto-break-desktop.jpg`, `monitor-auto-break-viewport.jpg`, `monitor-paused-desktop.jpg`

![Przerwa automatyczna — desktop](../output/playwright/monitor-auto-break-viewport.jpg)

![Monitor — mobile](../output/playwright/monitor-mobile.jpg)

## Pozostałe ograniczenia i aktywacja

Nie wykonano realnego SMTP, testu doręczenia do inboxa, renderu w Outlooku/Gmail/Apple Mail ani integracyjnego testu zewnętrznego unsubscribe endpointu. Podpis jest zgodny z baseline; działanie wdrożonego endpointu pozostaje niezależnym dowodem. Nie testowano natywnego schowka aplikacji Word ani wszystkich przeglądarek. Logi przeglądarki IAB zawierały błędy MutationObserver; aplikacja nie używa tego API, ale źródło tych wpisów nie zostało jednoznacznie ustalone. Nie deklarujemy czystej konsoli. Funkcje opisane wyżej zostały sprawdzone przez rzeczywisty UI. Silnik formatowania używa `execCommand`, więc przyszłe zmiany przeglądarki wymagają regresji.

one.com potwierdza [25 wiadomości/5 min i 250/godz. oraz limity odbiorców](https://help.one.com/hc/en-us/articles/115005594205-What-limitations-apply-to-email-size-and-sending). Aplikacja utrzymuje zapas 20/5 min i 200/godz.; inne klienty pocztowe mogą nadal zużyć pozostały limit. Nie można obiecać bezbłędnej akceptacji konta ani finalnego doręczenia.

Operacyjna migracja/backup i uruchomienie nowego procesu na prawdziwej bazie wymagają osobnego zakresu aktywacji. Banner assets i SQLite trzeba zachowywać razem. Nie wprowadzono automatycznego kasowania assetów. Kolejki legacy bez nowego fingerprintu SMTP wymagają osobnej kontroli przed wznowieniem realnych prób. Powiadomienie admina może czekać do końca kampanii; niepewne powiadomienia nie są ponawiane automatycznie.

Context Pack: AGENTS/README/brief przejrzane; jeden rejestr wymagań i dokładnie jeden wpis Change Log tego zadania. GitHub/deploy: bez zmian; źródła lokalnie niezatwierdzone.
