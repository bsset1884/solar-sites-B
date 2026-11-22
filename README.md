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
npm run 