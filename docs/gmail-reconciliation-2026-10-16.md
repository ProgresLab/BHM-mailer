# Rozliczenie Gmail — 2026-10-16

Task: `BHM-GMAIL-RECONCILIATION-2026-10-16`. Operacja jednorazowa, jawnie autoryzowana przez użytkownika, po zakończeniu kolejki. Bez nowej wysyłki, restartu, migracji, deployu i zmian DNS/tempa SMTP.

## Zakres i wynik

Root `C:\Users\info\AGENTS\BHM Mailer`, `main`, origin `ProgresLab/BHM-mailer`, początkowy lokalny i świeży remote HEAD `ddec813f50b3f2990e20500534b3f63dbdc40069`. Przed zadaniem były lokalne zmiany aktywacji w README/brief oraz nieśledzony raport aktywacji; zachowano je i wyłączono z tego commita.

Operacyjna baza: `data/bhm_mailer.sqlite3`. Kampania **38**, nazwa i temat „Specialty Raw Materials & Sourcing | BHM Chemicals”, 1000 odbiorców, rozpoczęcie prób 2026-10-16 08:27:23 UTC, koniec kolejki 18:27:17 UTC. `campaigns.status` i `campaign_execution.state`: `completed`; 1004 próby SMTP, brak otwartych prób, powiadomień queued/sending i rezerwacji konta. Inne stare kolejki pozostają interrupted/manual-paused. Port 8000 już przed pracą odmawiał połączenia; 8017/8018 również bez listenerów. Nie uruchamiano ani nie zatrzymywano aplikacji. Odczyt listy procesów CIM był niedostępny, dlatego nie przypisujemy obecnego stanu do historycznego PID.

Gmail: istniejący konektor, potwierdzony dostęp do profilu, paginacji, pełnego MIME, załącznika EML i RAW. Cztery zapytania `in:anywhere after:2026/10/16`, obejmujące marketing, temat kampanii oraz osobno domenę/BHM + unsubscribe. Liczby wyników: **543 / 70 / 533 / 530**, odpowiednio 6/1/6/6 stron. Unia: **555 unikalnych Gmail message IDs**, odczytanych bez utraconych rekordów. Końcowe powtórzenie wszystkich zapytań dało te same zbiory, bez nowych ID. To zamknięty skan z dnia 16 października, a nie dowód braku przyszłych zwrotów.

Odczytano 510 raportów DSN i 10 potwierdzonych wypisań, czyli **520 unikalnych strukturalnych zdarzeń**. Dwa dalsze raporty tekstowe zachowano do ręcznego przeglądu. Pozostałe 33 wiadomości to 32 bez zmiany (odpowiedzi/autorespondery, wcześniejsze testy i jeden niezwiązany wynik wyszukiwarki) oraz wypisanie dotyczące innej kampanii. Nie kontynuowano analizy niezwiązanego wyniku ani nie przenoszono go do historii operacyjnej.

| Wynik | Liczba |
| --- | ---: |
| Kontakty zmienione na invalid | 354 |
| Kontakty zmienione na unsubscribed | 10 |
| Finalne DSN failed powiązane z historyczną akceptacją: bounced_later | 430 |
| Opóźnienia | 55: 54 zweryfikowane + 1 w przeglądzie źródła |
| Przypadki wymagające przeglądu | 72: 44 inne DSN, 26 niepełnych powiązań/uwierzytelnienia, 2 raporty tekstowe |
| Powiadomienie unsubscribe z innej kampanii, wyłączone | 1 |

354 invalid obejmuje 126 trwałych błędów DNS, 90 jednoznacznych błędów skrzynki i 138 pełnych odpowiedzi Microsoft DBEB. W 32 raportach potwierdzono problem polityki/nadawcy; kontakty nie zostały przez to oznaczone invalid. Kategorie przeglądu opisują niepewność przyczyny lub powiązania; jednoznaczny, uwierzytelniony `Action: failed` z dokładnym Message-ID może potwierdzać późniejszy bounce bez ustalenia, że skrzynka nie istnieje. Dlatego 430 późniejszych bounce przekracza liczbę wyłączonych kontaktów.

## Reguły dowodowe

Parser jest deterministyczny: MIME/DSN przez bibliotekę `email`, odbiorca Original/Final-Recipient, Action, Status, Diagnostic-Code, nagłówki oryginału, identyfikator wiadomości, czas i pochodzenie. Sześć wiadomości zawierających specjalne części MIME ponownie pobrano w RAW. Obsłużono także niepoprawnie zakodowany base64 `message/delivery-status`. Nie znaleziono `details.txt`; parser i test obsługują ten wariant. Obrazów/logo nie pobierano do analizy DSN.

Zmiana kontaktu wymaga zgodnego adresu i dokładnego Message-ID zaakceptowanej próby w kampanii, poprawnego czasu, przekierowania do marketing oraz zgodnego DKIM w zewnętrznym werdykcie `mx.google.com`. Sam temat, kod 550 lub podpis pośredniego forwardera nie wystarczają. Brak wystarczającego oryginalnego uwierzytelnienia trafia do raportu przeglądu. Nie diagnozowano domen przez nowe zapytania DNS; podstawą trwałych błędów domeny jest uwierzytelniony finalny DSN z NXDOMAIN.

Microsoft: tylko pełny `550 5.4.1 Recipient address rejected: Access denied`, adres dokumentacji EXOSmtpErrors i host `*.prod.outlook.com` przy poprawnym przypisaniu odbiorcy kwalifikują jako błąd skrzynki. Microsoft opisuje taki komunikat jako DBEB dla nieprawidłowego odbiorcy: [oficjalna dokumentacja](https://learn.microsoft.com/en-us/troubleshoot/exchange/email-delivery/ndr/fix-error-code-550-5-4-1). Niepełny komunikat pozostaje do przeglądu.

Wypisania: powiadomienia do `info@`, nadawca `info@bhm-chemicals.com`, zgodny DKIM domeny, zadeklarowane źródło publicznego endpointu, zgodny email/token/ID kampanii i timestamp z niezmiennego snapshotu linku; data po akceptacji. Tokenów i treści oryginalnych wiadomości nie publikujemy. Wypisanie wygrywa z invalid. Import kontaktów zachowuje oba statusy, wybór/nowa kampania i istniejąca kolejka wykluczają je. Dodano również warunek w workerze, aby odpowiedź recipient-failure z już rozpoczętej próby nie mogła nadpisać późniejszego wypisania. Ten warunek jest zmianą źródła, bez restartu runtime.

## Backup, zapis i niezależny readback

Backup SQLite API obejmujący ewentualny WAL: prywatny `backups/reconciliation-20261016T183854916141Z/`, wraz z kompletem dwóch plików `uploads/campaign_assets`. SQLite SHA-256: `a473237a6a03c25a1ffafd4f2c26feb2cdece09b5dcdffc4351252c610c1e6b2`. Porównano logiczną zgodność źródła i backupu oraz hashe zasobów. Integralność OK, FK 0.

Prywatny manifest zawiera plan: stare/nowe statusy, przyczynę, identyfikator dowodu i Gmail ID. Wykonano zapis na izolowanej kopii, odczyt z nowego połączenia i ponowny import bez zmian. Następnie `BEGIN IMMEDIATE` w operacyjnej bazie ponownie sprawdził zakończenie kolejki, komplet danych względem backupu i identyczność planu. Zapis operacyjny i niezależny readback są identyczne z symulacją.

Zakres zapisów: **364 kontakty** (tylko status/updated_at), **430 email_sends** (tylko status, trace_status/detail/source i czasy finalnego dowodu), **515 dopisanych execution_events** z dowodami i zmianami. Bez nowych tabel/kolumn. Wszystkie inne tabele, wcześniejsze zdarzenia, selekcje i snapshoty pozostały identyczne. Zachowano wszystkie 1000 `accepted_at`, odpowiedzi SMTP, sent_at, Message-ID i 1004 historyczne próby. Po zapisie: kontakty w kampanii 636 active / 354 invalid / 10 unsubscribed; rekordy wysyłki 570 accepted_by_smtp / 430 bounced_later. Kampania nadal completed, a nie „dostarczona”.

Dowody i raport przeglądu są wyłącznie w ignorowanym `output/reconciliation-38/`: `manifest.json`, `applied-readback.json`, pełne MIME/RAW, `final-search-check.json`, `smtp-diagnostics-redacted.json`, testy. Nie dodano unsubscribe_events, które mogłyby uruchomić powiadomienie SMTP. Dowodem zewnętrznych wypisań jest istniejący ledger execution_events. Powtórka deduplikuje Gmail/DSN na podstawie identyfikatora raportu, odbiorcy i treści zdarzenia; nie tworzy kolejnych mutacji ani wpisów dla tego samego dowodu.

## Cztery odmowy SMTP 4xx

Każdy przypadek: `451 4.7.1 [R6] You have more than 50 failed deliveries the last hour, try later`. Pełne odpowiedzi z ID serwera zachowano w prywatnym raporcie po redakcji adresów.

| Próba | UTC | Europe/Warsaw |
| --- | --- | --- |
| 402 | 10:54:15 | 12:54:15 |
| 561 | 12:37:15 | 14:37:15 |
| 721 | 14:39:13 | 16:39:13 |
| 956 | 17:55:22 | 19:55:22 |

To ochronna odmowa serwera wyjściowego związana z liczbą nieudanych doręczeń konta, zgłoszona przy RCPT; nie dowód nieistnienia tych czterech odbiorców ani błędu sieci. Wszystkie cztery rekordy ostatecznie uzyskały akceptację po ręcznych wznowieniach, a wcześniejsze odmowy pozostały w historii.

Zmierzone 1004 starty: minimalny odstęp **20.0025 s**, najwyżej **15/5 min** i **175/h**. Nie ma dowodu, że samo tempo 20 s/przerwy było przyczyną tych odmów. Udokumentowane zwykłe limity one.com to 25/5 min i 250/h, lecz nie tłumaczą progu R6: [limity dostawcy](https://help.one.com/hc/en-us/articles/115005594205-What-limitations-apply-to-email-size-and-sending). Próg 50 nieudanych doręczeń jest dowodem z rzeczywistej odpowiedzi SMTP; nie dopowiadamy nieopublikowanego zakresu licznika (np. domena/IP zamiast konta).

Rekomendacja na następną kampanię: wykorzystać oczyszczoną listę, rozstrzygnąć raporty polityki i niepełne dowody, rozpocząć mniejszą partią i obserwować nowe DSN; samo wydłużenie przerwy nie naprawia błędnej listy. Dla regularnych kampanii rozważyć usługę newsletterową — taką rekomendację podaje też one.com. Bez zmiany obecnego harmonogramu lub dostawcy w tym zadaniu.

## Walidacja i granice

57 izolowanych testów (47 dotychczasowych + 10 nowych), compileall. Obowiązkowe przypadki: trwały bounce, delay, unsubscribe, fałszywy raport, autoresponder, duplikat, obcy odbiorca/kampania, reimport, wykluczenie przez nową i istniejącą kolejkę, konflikt zapisu i priorytet wypisania podczas SMTP. Walidacja backupu/symulacji/całych tabel/readback i replay dodatkowo na rzeczywistych danych prywatnych.

Nie zmieniono żadnej etykiety, flagi odczytu ani wiadomości Gmail; nie wykonano nowej próby SMTP, restartu, migracji ani deployu. Nie tworzono procesów ani portów QA. Aplikacja pozostaje zatrzymana jak na początku. Nowe źródło workera nie zostało aktywowane; przyszły start nadal wymaga uwzględnienia recovery starych kolejek. Późniejsze DSN mogą wymagać kolejnego, osobno zleconego skanu; nie utworzono automatyzacji.

Context Pack Closeout: AGENTS przejrzano bez zmiany odpowiedzialności; README i brief opisują narzędzie, bieżący wynik oraz granice runtime. Jeden rejestr Requirements & Acceptance i dokładnie jeden datowany wpis tego zadania w Change Log. Publikacja obejmuje wyłącznie źródło, syntetyczne testy i ten zredagowany raport; prywatne dowody i wcześniejsze lokalne zmiany aktywacji pozostają poza commitem.
