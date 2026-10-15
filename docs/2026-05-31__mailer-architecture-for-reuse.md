# Struktura i zasada działania aplikacji mailingowej

Data opracowania: 2026-05-31

Źródła: analiza lokalnego projektu BHM Mailer: `README.md`, `requirements.txt`, `start.bat`, `app/main.py`, `app/db.py`, `app/importer.py`, `app/email_renderer.py`, `app/mailer.py`, `app/models.py`, szablony Jinja i `app/static/app.js`.

Ten dokument opisuje realny mechanizm aktualnej aplikacji i pokazuje, jak wykorzystać go jako wzorzec dla nowej firmy. Nie jest to gotowa porada prawna ani pełny system compliance dla masowego email marketingu.

## 1. Cel aplikacji

Aplikacja jest lokalnym narzędziem operacyjnym do:

- importu i porządkowania kontaktów,
- tworzenia prostych kampanii email w jednym języku,
- generowania zgodnego z Outlookiem HTML emaila i wersji plain text,
- ręcznego wyboru odbiorców,
- wysyłania wiadomości przez SMTP albo zapisu w trybie dry-run,
- zapisu historii każdej wysyłki jako snapshotu,
- obsługi wypisu z listy,
- importu zewnętrznego Message Trace CSV po wysyłce,
- eksportu statusów kampanii do CSV.

To nie jest platforma typu Mailchimp/Brevo. To lokalny panel dla małego zespołu, który chce kontrolować listę, treść, odbiorców i statusy bez pełnej automatyzacji marketing automation.

## 2. Stack narzędzi

| Warstwa | Technologia | Rola |
|---|---|---|
| Backend HTTP | FastAPI | routing, formularze, endpointy JSON, background task |
| Serwer lokalny | Uvicorn | uruchomienie aplikacji na `127.0.0.1:8000` |
| Widoki | Jinja2 | HTML panelu administracyjnego |
| Baza | SQLite | lokalny zapis kontaktów, kampanii, wysyłek i wypisów |
| Import XLSX | openpyxl | odczyt arkuszy Excel |
| SMTP | Python `smtplib` | realna wysyłka emaili |
| Email MIME | `email.mime.*` | multipart/alternative, HTML, plain text, inline logo |
| Konfiguracja | `.env` + `python-dotenv` | SMTP, adresy nadawcy, opóźnienia, sekret wypisu |
| Frontend panelu | HTML/CSS/vanilla JS | checkboxy, liczniki wyboru, polling statusu |
| Start lokalny | `start.bat` | venv, zależności, `.env`, start serwera, otwarcie przeglądarki |

Zależności z `requirements.txt`: `fastapi`, `uvicorn[standard]`, `jinja2`, `openpyxl`, `python-dotenv`, `python-multipart`.

## 3. Architektura katalogów

```text
BHM Mailer/
  app/
    main.py              # trasy HTTP, workflow UI, import trace, export CSV
    db.py                # SQLite, inicjalizacja schematu, migracje addytywne
    models.py            # walidacje, statusy, normalizacja emaili, raport importu
    importer.py          # import paste/XLSX, klasyfikacja PL/INTERNATIONAL, upsert
    email_renderer.py    # render HTML/text emaila i stopki unsubscribe
    mailer.py            # SMTP, snapshoty, statusy wysyłki, podpisane linki wypisu
    templates/           # widoki Jinja panelu
    static/
      app.js             # polling statusu, checkboxy, live update UI
      styles.css         # styl panelu
      assets/            # logo używane w emailach
  data/
    bhm_mailer.sqlite3   # lokalna baza, generowana automatycznie
  uploads/               # zaimportowane pliki XLSX
  .env.example           # przykład konfiguracji SMTP
  requirements.txt
  start.bat
```

## 4. Model danych

### `contacts`

Reprezentuje pojedynczy adres email.

Kluczowe pola:

- `email` - unikalny adres, normalizowany do lowercase,
- `company_name`, `contact_name`, `industry`, `notes` - metadane,
- `country_group` - `PL` albo `INTERNATIONAL`,
- `language` - `pl` albo `en`,
- `status` - `active`, `unsubscribed`, `bounced`, `invalid`,
- `unsubscribe_token` - losowy token do wypisu,
- `source`, `source_sheet` - źródło importu,
- `last_sent_at`, `created_at`, `updated_at`.

Zasada: kontakt wypisany, bounced albo invalid nie wraca automatycznie do `active` podczas importu.

### `campaigns`

Reprezentuje kampanię.

Kluczowe pola:

- `name` - nazwa kampanii,
- `language` - język kampanii,
- `subject` - temat; obecnie równy nazwie kampanii,
- `body` - treść wpisana przez użytkownika,
- `html`, `text` - wyrenderowane snapshoty kampanii,
- `status` - `draft`, `approved`, `sending`, `completed`, `completed_with_errors`, `stopped`,
- `created_at`, `approved_at`, `completed_at`.

### `email_sends`

Reprezentuje konkretną próbę wysyłki kampanii do jednego kontaktu.

Kluczowe pola:

- `campaign_id`, `contact_id`, `email`,
- `subject`, `html_snapshot`, `text_snapshot`,
- `status` - np. `pending`, `sending`, `accepted_by_smtp`, `smtp_failed`, `delivered_by_trace`,
- diagnostyka SMTP: `smtp_code`, `smtp_response`, `smtp_user`, `header_from`, `reply_to`, `envelope_from`, `envelope_to`, `message_id`,
- trace: `trace_status`, `trace_detail`, `trace_source`,
- czasy: `started_at`, `accepted_at`, `final_status_at`, `last_checked_at`, `sent_at`.

Zasada: każdy odbiorca dostaje osobny snapshot treści z własnym linkiem wypisu. Zmiana kampanii po wysyłce nie zmienia historii wysłanych wiadomości.

### `unsubscribe_events`

Rejestruje wypis:

- `contact_id`,
- `email`,
- `token`,
- opcjonalnie `source_campaign_id`,
- `created_at`,
- `notification_sent`.

## 5. Główne funkcje aplikacji

### Dashboard

Pokazuje:

- liczbę wszystkich kontaktów,
- aktywne kontakty,
- podział PL/INTERNATIONAL,
- wypisanych,
- bounced/invalid,
- ostatnie kampanie i podstawowe liczniki statusów.

### Import kontaktów

Obsługuje:

- kopiuj-wklej listy adresów,
- plik XLSX,
- wiele arkuszy,
- wiele emaili w jednej komórce,
- aliasy kolumn typu `Company name`, `Company name & country`, `email`, `email address`, `industry`, `Inudstry`, `date sent`, `comments`,
- tryb klasyfikacji: Auto / Polska / Poza Polską.

### Lista i edycja kontaktów

Funkcje:

- filtrowanie po grupie, języku, statusie, branży i tekście,
- limit widoku 500 rekordów,
- edycja pojedynczego kontaktu,
- akcje masowe: ustaw PL, ustaw INTERNATIONAL, ustaw active, ustaw unsubscribed, ustaw invalid.

### Tworzenie kampanii

Wersja aktualna jest single-language:

- nazwa kampanii jest równocześnie tematem emaila,
- użytkownik wybiera język `pl` albo `en`,
- wpisuje jedną treść wiadomości,
- aplikacja generuje HTML email i plain text,
- kampania startuje jako `draft`.

### Podgląd i zatwierdzenie

Użytkownik sprawdza HTML/plain text, a potem zatwierdza kampanię. Dopiero status `approved` pozwala przejść do wyboru odbiorców.

### Wybór odbiorców

Odbiorcy są wybierani ręcznie checkboxami, z filtrami:

- grupa,
- język,
- tylko aktywni,
- search.

Kontakty `unsubscribed`, `invalid`, `bounced` są blokowane w UI i ponownie sprawdzane w backendzie.

### Wysyłka kampanii

Mechanizm:

- backend sprawdza status kampanii,
- sprawdza aktywnych odbiorców,
- sprawdza konfigurację SMTP,
- wymaga potwierdzenia wysyłki,
- pokazuje ostrzeżenie przy kampanii powyżej 100 odbiorców,
- wymaga dodatkowego potwierdzenia powyżej 500 aktywnych odbiorców,
- tworzy wpisy `email_sends` jako `pending`,
- uruchamia `send_pending_campaign` w tle przez FastAPI `BackgroundTasks`.

### Historia i live progress

Historia pokazuje:

- listę kampanii,
- status kampanii,
- liczniki statusów,
- konfigurację SMTP aktualną dla nowych wysyłek,
- rzeczywistą tożsamość SMTP zapisaną przy wybranym sendzie,
- snapshot HTML/plain text wysłanej wiadomości,
- status każdego odbiorcy,
- import trace,
- eksport CSV.

Frontend odpytuje endpoint:

```text
GET /campaigns/{campaign_id}/status.json
```

co 2 sekundy. Nie ma WebSocketów.

### Import Message Trace CSV

Po wysyłce można wgrać CSV z zewnętrznego trace/delivery report. Dopasowanie jest po:

- emailu odbiorcy,
- temacie,
- czasie wysyłki w oknie +/- 24h,
- senderze, jeżeli występuje w CSV.

Mapowanie:

- `Delivered` -> `delivered_by_trace`,
- `Failed` -> `failed_by_trace`,
- `Quarantined` -> `quarantined_by_trace`,
- `Pending` lub `Expanded` -> `delivery_pending`,
- nieznane wartości -> `delivery_unknown` albo zachowanie wcześniejszego `accepted_by_smtp`.

Trace nie nadpisuje chronionych statusów typu `smtp_failed`, `skipped_unsubscribed`, `skipped_invalid`, `dry_run`.

### Wypis z listy

Aktualna aplikacja ma dwa mechanizmy:

- lokalny endpoint `/unsubscribe/{token}`,
- publiczny podpisany URL do zewnętrznego endpointu, konfigurowany przez `PUBLIC_UNSUBSCRIBE_BASE_URL`.

Link publiczny zawiera:

- `email`,
- `token`,
- `lang`,
- `campaign_id`,
- `ts`,
- `sig`.

`sig` to HMAC-SHA256 z payloadu:

```text
email|token|lang|campaign_id|ts
```

podpisany sekretem `UNSUBSCRIBE_SECRET`.

## 6. Algorytm działania end-to-end

```text
1. Start aplikacji
   - start.bat tworzy venv, instaluje zależności, kopiuje .env.example do .env, startuje Uvicorn.
   - FastAPI wykonuje init_db() i tworzy/migruje SQLite.

2. Import kontaktów
   - użytkownik wkleja adresy albo uploaduje XLSX.
   - importer wykrywa kolumnę email i metadane.
   - adresy są dzielone po spacjach, przecinkach, średnikach i nowych liniach.
   - email jest normalizowany i walidowany regexem.
   - grupa/język są nadawane ręcznie albo automatycznie.
   - baza robi upsert po emailu.
   - istniejące pola są uzupełniane tylko, gdy były puste.
   - statusy unsubscribed/bounced/invalid nie są cofane do active.

3. Utworzenie kampanii
   - użytkownik podaje nazwę, język i treść.
   - subject = name.
   - renderer tworzy HTML table-based i plain text.
   - kampania trafia do bazy jako draft.

4. Zatwierdzenie kampanii
   - status zmienia się z draft na approved.
   - ustawiany jest approved_at.

5. Wybór odbiorców
   - UI filtruje kontakty.
   - użytkownik zaznacza checkboxy.
   - backend deduplikuje ID i przepuszcza tylko aktywnych.

6. Przygotowanie wysyłki
   - aplikacja sprawdza konfigurację SMTP i unsubscribe.
   - dla każdego kontaktu zapewnia unsubscribe_token.
   - buduje podpisany URL wypisu.
   - wstawia spersonalizowany html_snapshot/text_snapshot do email_sends jako pending.
   - kampania dostaje status sending.

7. Wysyłka w tle
   - dla każdego pending:
     - status -> sending,
     - tworzony jest Message-ID,
     - budowany jest MIME multipart/related + multipart/alternative,
     - dołączane jest inline logo, jeżeli HTML używa CID,
     - smtplib łączy się przez SSL albo STARTTLS,
     - SMTP login,
     - sendmail(envelope_from, envelope_to, message),
     - sukces -> accepted_by_smtp,
     - wyjątek SMTP -> smtp_failed, rate_limited albo delivery_pending,
     - stały błąd odbiorcy może oznaczyć kontakt jako bounced/invalid.
   - między emailami aplikacja czeka EMAIL_SEND_DELAY_SECONDS.

8. Finalizacja kampanii
   - jeżeli są pending/sending, kampania zostaje sending.
   - jeżeli są błędy, kampania -> completed_with_errors.
   - jeżeli nie ma błędów, kampania -> completed.

9. Weryfikacja po wysyłce
   - accepted_by_smtp oznacza tylko przyjęcie przez serwer SMTP.
   - użytkownik importuje Message Trace CSV.
   - aplikacja aktualizuje statusy finalne tam, gdzie trace potwierdza wynik.
```

## 7. Statusy i ich znaczenie

### Statusy kontaktów

| Status | Znaczenie |
|---|---|
| `active` | może być wybrany do wysyłki |
| `unsubscribed` | wypisany, nie powinien otrzymywać kampanii |
| `bounced` | adres odbił albo jest problematyczny |
| `invalid` | adres błędny lub niepoprawny |

### Statusy kampanii

| Status | Znaczenie |
|---|---|
| `draft` | kampania utworzona, niezatwierdzona |
| `approved` | gotowa do wyboru odbiorców |
| `sending` | wysyłka w toku |
| `completed` | zakończona bez błędów według lokalnych statusów |
| `completed_with_errors` | zakończona z błędami lub niepewnymi statusami |
| `stopped` | status przewidziany w modelu, brak pełnego workflow stopowania |

### Statusy wysyłki

| Status | Znaczenie |
|---|---|
| `pending` | wpis czeka w kolejce |
| `sending` | aktualnie przetwarzany email |
| `accepted_by_smtp` | serwer SMTP przyjął wiadomość, ale to nie dowód dostarczenia |
| `smtp_failed` | błąd SMTP lub konfiguracji |
| `rate_limited` | prawdopodobny throttling/rate limit |
| `delivery_pending` | tymczasowy albo nieostateczny wynik |
| `delivered_by_trace` | trace potwierdził dostarczenie |
| `failed_by_trace` | trace potwierdził porażkę |
| `quarantined_by_trace` | trace potwierdził kwarantannę |
| `bounced_later` | późniejszy bounce, jeśli zostanie potwierdzony |
| `skipped_unsubscribed` | pominięty, bo kontakt wypisany |
| `skipped_invalid` | pominięty, bo invalid/bounced/brak kontaktu |
| `skipped_duplicate` | przewidziane dla duplikatów |
| `cancelled` | przewidziane dla anulowania |
| `dry_run` | SMTP nie był skonfigurowany, zapisano próbę bez wysyłki |

## 8. Zasada bezpieczeństwa i kontroli

Aplikacja ogranicza ryzyko przez:

- dry-run, gdy SMTP nie jest skonfigurowany,
- blokadę realnej wysyłki bez pełnej konfiguracji SMTP,
- blokadę realnej wysyłki bez `UNSUBSCRIBE_SECRET`,
- blokadę masowej wysyłki przy lokalnym unsubscribe URL,
- ręczne zatwierdzenie kampanii przed wysyłką,
- dodatkowy checkbox powyżej 500 odbiorców,
- osobny snapshot per odbiorca,
- redakcję sekretów w logach i eksporcie,
- nieuwalnianie statusów `unsubscribed`, `bounced`, `invalid` przez import,
- rozróżnienie `accepted_by_smtp` od realnego dostarczenia.

## 9. Ograniczenia aktualnej aplikacji

Techniczne:

- brak logowania użytkowników i ról,
- brak pracy wieloużytkownikowej,
- brak kolejki zewnętrznej typu Redis/Celery,
- background task działa w procesie aplikacji,
- SQLite jest dobre lokalnie, ale nie dla wielu operatorów i wysokiej skali,
- brak retry queue z harmonogramem,
- brak API do zarządzania kampaniami z zewnątrz,
- brak edytora drag-and-drop emaili,
- brak A/B testów,
- brak szablonów kampanii jako osobnych encji,
- brak automatycznego importu bounce/webhooków od dostawcy,
- brak natywnej integracji z Mailgun/Brevo/SendGrid/Amazon SES,
- brak tracking pixela i click trackingu,
- brak harmonogramu wysyłki,
- brak pełnego audytu operacji użytkowników,
- brak testów automatycznych w projekcie.

Operacyjne:

- `accepted_by_smtp` nie oznacza dostarczenia do inboxa,
- limity dostawcy SMTP trzeba znać poza aplikacją,
- deliverability zależy od domeny, SPF/DKIM/DMARC, reputacji i treści,
- aplikacja nie weryfikuje prawnej podstawy kontaktu,
- aplikacja nie rozwiązuje consent management dla różnych jurysdykcji,
- publiczny endpoint unsubscribe musi istnieć i używać tego samego sekretu HMAC.

## 10. Co trzeba zmienić dla nowej firmy

Elementy obowiązkowe:

- nazwa firmy w UI i emailach,
- logo w `app/static/assets/`,
- dane stopki firmowej w `email_renderer.py`,
- adres kontaktowy w `email_renderer.py`,
- `.env.example` i realny `.env`,
- domena nadawcy,
- `SMTP_HOST`, `SMTP_PORT`, SSL/TLS,
- `SMTP_USER`, `SMTP_FROM_EMAIL`, `SMTP_REPLY_TO`, `SMTP_ENVELOPE_FROM`,
- publiczny adres wypisu,
- sekret `UNSUBSCRIBE_SECRET`,
- treści komunikatów wypisu,
- polityka opóźnienia `EMAIL_SEND_DELAY_SECONDS`,
- zasady importu kolumn z Excela, jeżeli firma ma inne pliki.

Elementy rekomendowane:

- przenieść stałe BHM z kodu do konfiguracji,
- dodać tabelę `settings` albo plik `company_profile.yml`,
- dodać logowanie operatora, jeżeli aplikacja ma działać poza komputerem lokalnym,
- zastąpić SMTP dostawcą transactional/bulk email z webhookami,
- dodać bounce webhook,
- dodać testy importera, renderera, mailera i trace importu,
- dodać mechanizm zatrzymania kampanii,
- dodać stronę test-send do jednego odbiorcy przed kampanią,
- dodać walidację DNS/checklistę SPF/DKIM/DMARC,
- dodać osobną encję `email_templates`,
- dodać eksport/backup bazy.

## 11. Minimalna architektura dla nowego projektu

### Wersja lokalna, podobna do obecnej

```text
FastAPI + Jinja UI
SQLite
SMTP provider
public unsubscribe endpoint
CSV/XLSX import
manual recipient selection
background task in-process
CSV trace import
```

Dobra dla:

- małej firmy,
- ręcznych kampanii,
- pojedynczego operatora,
- wolumenów testowanych stopniowo,
- sytuacji, gdzie kontrola jest ważniejsza niż automatyzacja.

### Wersja produkcyjna

```text
FastAPI/Next.js admin UI
PostgreSQL
Redis/Celery/RQ albo kolejka dostawcy
Email provider API: SES/Mailgun/Brevo/SendGrid
webhooki delivery/bounce/complaint/unsubscribe
auth + role
audit log
template manager
domain/DNS verification
backup
monitoring
```

Dobra dla:

- wielu operatorów,
- większych list,
- kampanii cyklicznych,
- wymogów audytu,
- finalnych statusów z webhooków zamiast ręcznego trace CSV.

## 12. Proponowany backlog przeniesienia na inną firmę

1. Wydzielić profil firmy:
   - `company_name`,
   - `contact_email`,
   - adres rejestrowy,
   - NIP/VAT lub odpowiednik,
   - logo,
   - domyślny język,
   - domyślny footer.

2. Wydzielić konfigurację dostawcy email:
   - SMTP/API provider,
   - from/reply-to/envelope-from,
   - limity godzinowe/dzienne,
   - opóźnienie między wiadomościami.

3. Zostawić obecne statusy jako rdzeń:
   - `accepted_by_smtp` jako status techniczny,
   - osobne statusy finalne z trace/webhooka.

4. Dodać compliance checklist:
   - źródło kontaktu,
   - status zgody/podstawy kontaktu,
   - data pozyskania,
   - łatwy unsubscribe,
   - suppression list.

5. Dodać testy:
   - normalizacja emaila,
   - import XLSX,
   - deduplikacja,
   - ochrona unsubscribed,
   - generowanie linku HMAC,
   - render HTML/text,
   - klasyfikacja błędów SMTP,
   - import trace.

## 13. Najważniejszy wzorzec do skopiowania

Najbardziej wartościowa zasada tej aplikacji:

```text
Kontakt -> Kampania -> Snapshot per odbiorca -> Kontrolowana wysyłka -> Status techniczny -> Status finalny z trace/webhooka -> Historia i eksport
```

Nie należy kopiować na ślepo:

- stałych BHM,
- adresów domeny,
- konfiguracji one.com,
- danych stopki,
- progów wysyłkowych bez weryfikacji limitów nowego dostawcy,
- założenia, że SMTP acceptance oznacza dostarczenie.

## 14. Minimalny prompt/spec dla nowego projektu

```text
Zbuduj lokalną aplikację do kontrolowanej wysyłki kampanii email dla [NAZWA FIRMY].

Stack: FastAPI, Jinja2, SQLite, openpyxl, python-dotenv, SMTP przez smtplib.

Funkcje:
- import kontaktów z paste i XLSX,
- normalizacja i deduplikacja emaili,
- statusy kontaktów: active, unsubscribed, bounced, invalid,
- tworzenie kampanii single-language,
- generowanie HTML emaila table-based + plain text,
- ręczny wybór odbiorców z filtrami,
- snapshot wiadomości per odbiorca,
- podpisany link wypisu HMAC,
- wysyłka SMTP z opóźnieniem między wiadomościami,
- tryb dry-run,
- statusy: pending, sending, accepted_by_smtp, smtp_failed, rate_limited, delivery_pending, delivered_by_trace, failed_by_trace, quarantined_by_trace, skipped_*,
- live progress przez polling JSON,
- historia kampanii,
- import Message Trace CSV,
- eksport statusu kampanii do CSV.

Wymagania:
- nie wysyłaj do unsubscribed/bounced/invalid,
- nie przywracaj unsubscribed do active przez import,
- nie traktuj accepted_by_smtp jako dostarczenia,
- nie loguj sekretów,
- nie hardcoduj haseł,
- wszystkie dane firmy trzymaj w konfiguracji,
- przed realną wysyłką wymagaj pełnej konfiguracji SMTP i sekretu unsubscribe.
```
