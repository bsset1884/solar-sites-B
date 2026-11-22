# Solar Sites

een kleine webapp die gemaakt is voor de adviseurs van Praeter. Een adviseur maakt een acocunt aan, voegt klant locaties toe zoals naam van de klant, adres, coordinaten, dakoppervalk en vermogen van de panelen en ziet per locatie:

- hoeveel stroom de zonnepanelen naar de verwachting per jaar en per maand opleveren, berekend met PVGIS, de gratis zonne energiedienst van de Europese Commissie
- hoeveel van die stroom het huishouden zelf gebruikt met en zonder thuisbatterij, en dus wat de batterij plevert. De adviseur kiest zelf hoe groot de batterij is.

Een adviseuer ziet alleen zijn eigen locaties.

Backend: Python (FastAPI, SQLAlchemy, SQLite). Frontend: TypeScript (React, Vite).
Een Docker draait allebei.

## Hoe je moet starten:

docker build -t solar .
docker run -p 8000:8000 solar
```

Klik op die localhost link die je te verschijnen krijgt, en maak een account aan.

De database (een SQLite-bestand) staat in de container in `/app/data`. Wil je de gegevens
bewaren als de container wordt verwijderd? Start hem dan met een volume:
`docker run -p 8000:8000 -v solar-data:/app/data solar`.

Een overzicht van alle API-routes staat op <http://localhost:8000/api/docs> of <http://0.0.0.0:8000/api/docs>

### Zonder Docker (om aan de code te werken)

Je hebt Python 3.12 of nieuwer nodig, en Node 22 (20.19 of nieuwer werkt ook).

```bash
# backend: http://127.0.0.1:8000
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest                                                 # 60 tests
uvicorn app.main:app --reload

# frontend: http://localhost:5173 (stuurt /api door naar de backend)
cd frontend
npm ci
npm run dev
```

### Instellingen (omgevingsvariabelen, allemaal optioneel)

| Variabele | Standaard | Wat het doet |
|---|---|---|
| `DATA_DIR` | `backend/data` (`/app/data` in Docker) | Map waarin het databasebestand staat |
| `STATIC_DIR` | `backend/static` (`/app/static` in Docker) | De gebouwde frontend die op `/` wordt getoond |
| `PVGIS_BASE_URL` | `https://re.jrc.ec.europa.eu/api/v5_3` | Adres van de PVGIS-API |
| `PVGIS_TIMEOUT_SECONDS` | `30` | Na zoveel seconden stoppen we met wachten op PVGIS |
| `SESSION_TTL_SECONDS` | `604800` (7 dagen) | Hoe lang je ingelogd blijft |
| `COOKIE_SECURE` | `false` | De cookie altijd alleen via HTTPS laten versturen (bij HTTPS gebeurt dat al vanzelf) |
| `LOGIN_MAX_FAILURES` / `LOGIN_WINDOW_SECONDS` | `10` / `900` | Na hoeveel foute inlogpogingen, binnen hoeveel seconden, we even blokkeren |

## Keuzes, en waarom

### Techniek

- **FastAPI voor de backend.** Je beschrijft met Pydantic modellen wat er binnen mag
  komen. FastAPI controleert dat dan zelf en geeft per veld een duidelijke foutmelding.
  Controles als "wie is er ingelogd?" en "is deze locatie van jou?" schrijf je een keer
  (`CurrentUser`, `OwnSite`) en hergebruik je in elke route. Je krijgt er ook gratis
  API-documentatie bij. De routes zijn gewone functies; FastAPI voert ze naast elkaar uit,
  zodat de code simpel blijft.
- **SQLite met SQLAlchemy.** Geen aparte databaseserver nodig: alles staat in een
  bestand en dat past goed bij een container. SQLAlchemy zet ingevoerde waarden altijd
  veilig in de query (geen SQL-injectie). Overstappen naar PostgreSQL is later vooral
  een kwestie van een andere verbinding instellen.
- **React en TypeScript met Vite.** Vite bouwt snel en vraagt bijna geen instellingen.
  React Router regelt de pagina's. Een extra bibliotheek voor state is niet nodig:
  `useState` en één klein eigen hookje (`useApi`) zijn genoeg. De grafieken zijn gewoon
  HTML en CSS; voor twaalf staafjes en twee balken heb je geen grafiekbibliotheek nodig.
- **Een container, een adres.** FastAPI serveert ook de gebouwde Reactapp. De browser
  en de API zitten dus op hetzelfde adres. Daardoor werkt de inlogcookie zonder gedoe
  en is CORS niet nodig.

### Inloggen en beveiliging

| Risico | Wat de app daartegen doet |
|---|---|
| Wachtwoorden worden gestolen | Wachtwoorden worden versleuteld opgeslagen met **Argon2id**, met de instellingen die OWASP aanraadt (19 MiB geheugen, 2 rondes) en een salt. Minimaal 8 tekens. |
| Iemand steelt een sessie | De sessie staat in een cookie die **HttpOnly** is (JavaScript kan hem niet lezen), **SameSite=Strict** en via HTTPS ook **Secure**. Het token is 256 willekeurige bits. In de database staat alleen een **SHA-256-hash** ervan, dus een gelekte database levert geen werkende sessies op. Een sessie verloopt na 7 dagen, en bij **uitloggen wordt hij ook op de server verwijderd**. Bij elke nieuwe login krijg je een nieuw token (geen session fixation). |
| CSRF (een andere website laat jouw browser iets doen) | Elke sessie heeft een CSRF-token. Je krijgt het als `csrfToken` terug bij registreren, inloggen en `/api/me`. Bij POST, PUT en DELETE moet dat token in de header `X-CSRF-Token` staan, anders volgt **403**. SameSite=Strict en het feit dat de API alleen JSON accepteert, geven extra bescherming. De frontend bewaart het token alleen in het geheugen. |
| Wachtwoorden raden | Na 10 foute pogingen voor hetzelfde e-mailadres binnen 15 minuten volgt **429**, met in `Retry-After` hoe lang je moet wachten. Ook het goede wachtwoord werkt dan even niet. |
| Uitzoeken wie een account heeft (bij inloggen) | "Onbekend e-mailadres" en "fout wachtwoord" geven dezelfde melding en kosten even lang. (Bij registreren moet de app wel zeggen dat een e-mailadres al bestaat; dat vraagt de opdracht.) |
| De locaties van een ander bekijken of wijzigen | Elke vraag aan de database filtert op de ingelogde adviseur. De locatie van een ander geeft **404 en geen 403**, zodat niemand kan uitproberen welke nummers bestaan. Wie de eigenaar is, komt altijd uit de sessie, nooit uit wat er wordt meegestuurd. |
| Rare invoer | Alles wordt gecontroleerd op grenzen en lengte. Getallen moeten echte getallen zijn (dus geen `true` of `"52"`), en `NaN` en `Infinity` worden geweigerd. Onbekende velden worden genegeerd. Bij fouten volgt **422** met één melding per veld. |
| Vreemde scripts (XSS) en clickjacking | React zet alle tekst veilig op de pagina. Een **Content-Security-Policy** staat alleen scripts, stijlen en lettertypes van onze eigen site toe, en `frame-ancestors 'none'` en `X-Frame-Options: DENY` voorkomen dat een andere site onze pagina's in een frame laadt. Verder: `nosniff`, `Referrer-Policy: same-origin` en `Cache-Control: no-store` op alle API-antwoorden. |
| De container | Draait als gewone gebruiker, niet als root. De lettertypes zitten in de app zelf, dus de paginas halen niets op bij andere partijen. |

### HTTP-statuscodes

| Route | Gelukt | Fouten |
|---|---|---|
| `POST /api/register` | **201 Created**: er bestaat nu een nieuw account | 409 e-mailadres bestaat al · 422 ongeldige invoer |
| `POST /api/login` | **200 OK**: gegevens kloppen, de inlogcookie is gezet | 401 fout e-mailadres of wachtwoord · 422 velden ontbreken · 429 te vaak fout |
| `POST /api/logout` | **204 No Content**: gelukt, er hoeft niets terug. Ook zonder sessie 204, want het resultaat is hetzelfde | 403 wel een sessie, maar geen geldig CSRF-token |
| `GET /api/me` | **200** `{email, csrfToken}` | 401 niet ingelogd |
| `GET /api/sites` | **200** de lijst met jouw locaties | 401 |
| `POST /api/sites` | **201 Created**, met een `Location`-header naar de nieuwe locatie | 401 · 403 CSRF · 422 per veld |
| `GET /api/sites/{id}` | **200** | 401 · 404 bestaat niet *of is niet van jou* |
| `PUT /api/sites/{id}` | **200** de bijgewerkte locatie (PUT vervangt alle velden) | 401 · 403 · 404 · 422 |
| `DELETE /api/sites/{id}` | **204 No Content** | 401 · 403 · 404 |
| `GET /api/sites/{id}/production` | **200** | 401 · 404 · **422** PVGIS heeft geen gegevens voor deze plek · **502** PVGIS gaf een fout of onzin terug · **503** PVGIS is te druk · **504** PVGIS reageert te traag |
| `GET /api/sites/{id}/battery` | **200** | zoals bij production, plus 422 bij een ongeldige `capacityKwh` of `annualUseKwh` |

- **401 of 403?** 401 betekent: "we weten niet wie je bent" (geen of een verlopen
  sessie). 403 betekent: "we weten wie je bent, maar dit mag niet" (het CSRF-token ontbreekt).
- **Waarom 422 als PVGIS geen gegevens heeft?** Het verzoek is in orde en de locatie
  bestaat, maar op die plek kan niets berekend worden. Het probleem zit dus in de
  gegevens van de locatie. Het is geen fout van de server (5xx) en de locatie bestaat
  gewoon (geen 404). In het antwoord staat de reden van PVGIS, bijvoorbeeld:
  *"PVGIS cannot give an estimate for this location: Location over the sea."*
- **502, 503 en 504** betekenen: onze server werkt, maar de dienst erachter (PVGIS)
  gaf een fout, was te druk of reageerde niet op tijd. Later opnieuw proberen kan helpen.

Fouten komen terug als JSON: `{"detail": "..."}`, en bij 422 ook
`"errors": {"veld": "melding"}`.

### PVGIS

Alle vragen aan PVGIS gaan via de backend (`backend/app/pvgis.py`). PVGIS staat
rechtstreekse aanroepen vanuit een browser ook niet toe.

- **Opbrengst:** `PVcalc` met `optimalangles=1` en `loss=14` (%). De opdracht kent
  geen velden voor de hoek en de richting van het dak. Daarom gaan we uit van panelen
  in de beste hoek voor die plek. PVcalc geeft het gemiddelde over veel jaren
  (2005–2023 voor Europa).
- **Batterij:** daarvoor is de opbrengst per uur nodig. Die komt uit `seriescalc` voor
  2023 (het meest recente volledige jaar in PVGIS 5.3), met dezelfde panelen. We
  schalen die uurwaarden zo dat het jaartotaal gelijk is aan het gemiddelde van PVcalc.
  Zo komt het patroon uit echt weer, en tonen beide delen van de pagina dezelfde
  jaaropbrengst.
- **Onthouden (cache):** antwoorden worden per combinatie van breedtegraad,
  lengtegraad en kWp in het geheugen bewaard. De gegevens voor een plek veranderen
  niet, dus de tweede keer gaat direct en we blijven ruim onder de limiet van PVGIS
  (30 verzoeken per seconde). Fouten worden niet onthouden.
- **Fouten:** PVGIS antwoordt met 400 en een reden (bijvoorbeeld "Location over the
  sea") → wij geven 422 met die reden. 429 of 529 (overbelast) → 503. Een andere fout
  of een onleesbaar antwoord → 502. Te traag → 504. Geen verbinding → 502.

### Stroomverbruik van het huishouden (de aanname)

PVGIS weet niet hoeveel stroom een huishouden gebruikt en ook niet wanneer. Daarom
rekent de app zo:

1. **Hoeveel:** de adviseur vult het jaarverbruik in kWh in (dat staat op de
   energierekening van de klant). Met knoppen vul je het Nederlandse gemiddelde per
   huishouden in: 1.600 / 2.500 / 3.400 / 4.300 / 5.000 kWh voor 1 tot 5 personen
   ([overstappen.nl](https://www.overstappen.nl/energie/gemiddeld-energieverbruik/stroomverbruik/)).
   Standaard staat er 2.500 kWh, ongeveer een gemiddeld Nederlands huishouden.
2. **Wanneer:** dat totaal wordt verdeeld over de 8.760 uren van het jaar, naar
   *(gewicht van het uur van de dag) × (gewicht van de maand)*:
   - per uur: 's nachts weinig (koelkast, apparaten op stand-by), 's ochtends wat meer
     en het meest rond etenstijd (18:00–20:00), juist als de panelen weinig opleveren;
   - per maand: in de winter ongeveer 40% meer dan in de zomer (meer licht aan, vaker binnen).

   De gewichten staan in `backend/app/battery.py`. Ze volgen de klok zoals mensen
   die ervaren, inclusief zomertijd. PVGIS werkt in UTC, dus elk uur wordt omgerekend
   naar de tijdzone van de locatie.


**Waarom zo?** Het is in een zin uit te legge en het houdt rekening met het
belangrijkste voor een batterij: mensen gebruiken de meeste stroom 's avonds, als de zon
al weg is. Als je elk uur hetzelfde verbruik zou aannemen, lijkt het verbruik overdag
hoger dan het echt is. Dan schat je het eigen verbruik zonder batterij te hoog in en wat
de batterij oplevert te laag. Echte meetgegevens bijvoorbeeld van een slimme meter
zouden beter zijn. Omdat de API alleen het jaartotaal vraagt, kun je het profiel later
vervangen zonder iets aan de afspraken van de API te veranderen.

**De batterij** wordt uur voor uur doorgerekend. Het huis gebruikt eerst de zonnestroom
direct. Wat overblijft, laadt de batterij op en de rest gaat het net op. Heeft het huis meer
nodig dan de zon levert, dan helpt eerst de batterij en daarna het net. Aannames: de
ingevulde capaciteit is helemaal bruikbaar, **90% van de energie komt terug** uit de
batterij, laden en ontladen gaat met maximaal **0,5C** (een batterij van 10 kWh doet
hooguit 5 kW), de batterij laadt alleen met zonnestroom en is op 1 januari leeg.

**Wat `/battery` teruggeeft:** `productionKwh` (opbrengst), `consumptionKwh` (verbruik)
en voor beide situaties: `selfUsedKwh` (zonnestroom die thuis wordt gebruikt, direct of
via de batterij), `gridExportKwh` (naar het net), `gridImportKwh` (van het net),
`selfConsumptionPct` (zelf gebruikt gedeeld door opbrengst) en `selfSufficiencyPct`
(zelf gebruikt gedeeld door verbruik). Wat de batterij oplevert is
`withBattery.selfUsedKwh − withoutBattery.selfUsedKwh`.

Voorbeeld met echte PVGIS-gegevens (Den Haag, 52.08 / 4.31, 5 kWp, ongeveer 5.340 kWh
per jaar, verbruik 3.500 kWh): zonder batterij wordt ongeveer **25%** van de zonnestroom
thuis gebruikt, met een batterij van 5 kWh ongeveer **46%**, en met 10 kWh ongeveer
**49%**. De eerste kWh's batterij leveren het meest op; een grotere batterij voegt voor
dit huishouden weinig toe.

## Tests

`cd backend && pytest` draait 60 tests. Ze controleren onder meer dus registreren en
inloggen, CSRF, sessies, de limiet op inlogpogingen, dat adviseurs elkaars locaties niet
zien, de foutmeldingen per veld, de koppeling met PVGIS (met nagebootste antwoorden, ook
alle foutgevallen), het batterijmodel (de energie klopt, het rendement, het maximale
vermogen, zomertijd) en het serveren van de frontend met de juiste beveiligingsheaders.

## Mappenstructuur

```text
solar-sites-B/
├── Dockerfile                  2 stappen: eerst de frontend bouwen, dan de Python-server
├── .dockerignore               wat niet in de Docker-image hoort (node_modules, .venv, database)
├── .gitignore                  wat niet in Git hoort
├── README.md
├── backend/
│   ├── app/
│   │   ├── main.py             de FastAPI-app, beveiligingsheaders, de React-app serveren
│   │   ├── config.py           instellingen uit omgevingsvariabelen
│   │   ├── db.py               verbinding met de SQLite-database
│   │   ├── models.py           databasetabellen: users, sessions, sites
│   │   ├── schemas.py          wat de API ontvangt en teruggeeft (JSON in camelCase)
│   │   ├── errors.py           422 met een melding per veld, PVGIS-fouten
│   │   ├── security.py         wachtwoorden, sessies, CSRF
│   │   ├── rate_limit.py       limiet op inlogpogingen
│   │   ├── pvgis.py            koppeling met PVGIS, cache, foutafhandeling
│   │   ├── battery.py          verbruiksprofiel en batterijberekening
│   │   └── routers/
│   │       ├── auth.py         /api/register, /api/login, /api/logout, /api/me
│   │       └── sites.py        /api/sites… (locaties beheren, opbrengst, batterij)
│   ├── tests/                  60 tests (pytest)
│   ├── pyproject.toml          instellingen voor pytest en ruff
│   ├── requirements.txt        Python-pakketten voor de app
│   └── requirements-dev.txt    extra pakketten om te testen
└── frontend/
    ├── index.html
    ├── package.json            npm-pakketten en scripts
    ├── package-lock.json       vastgezette versies
    ├── tsconfig.json           TypeScript-instellingen
    ├── vite.config.ts          Vite-instellingen (stuurt /api door naar de backend)
    ├── public/favicon.svg
    └── src/
        ├── main.tsx            startpunt van de React-app
        ├── App.tsx             de pagina's (routes)
        ├── api.ts              alle aanroepen naar de backend (cookie + CSRF-header)
        ├── auth.tsx            bijhouden of je bent ingelogd
        ├── hooks.ts            gegevens laden, wachten tot de schuifbalk stilstaat
        ├── format.ts           getallen en maanden netjes tonen
        ├── styles.css          de vormgeving (geïnspireerd op sellavi.com; eigen logo, gratis lettertypes)
        ├── pages/              inloggen/registreren, overzicht, formulier, detailpagina
        └── components/         grafiek, batterijblok, formuliervelden, opmaak, iconen
```

## Grenzen en volgende stappen

- De limiet op inlogpogingen en de PVGIS cache staan in het geheugen. Dat werkt goed
  met een server. Met meerdere servers zou ik ze naar Redis verplaatsen.
- SQLite past bij een container. Voor veel gebruikers: PostgreSQL, met migraties (Alembic).
- De hoek en richting van het dak zitten niet in de opdracht dus de berekening gaat uit
  van de beste hoek. Met die velden erbij worden schattingen voor oost- of westdaken
  realistischer.
- Het verbruiksprofiel is algemeen. Met gegevens van een slimme meter wordt het
  batterijadvies persoonlijk.
- Er is nog geen bevestiging van het e-mailadres en geen "wachtwoord vergeten".
- Coordinaten typ je zelf in (het formulier heeft een link naar OpenStreetMap). Het
  adres automatisch omzetten naar coördinaten zou een mooie volgende stap zijn.

## Bronnen

Zonnegegevens: [PVGIS](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis_en)
© Europese Unie.

Webdesign en thema geïnspireerd door Sellavi.com