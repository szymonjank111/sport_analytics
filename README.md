# ⚽ Football Analytics Pipeline

Tygodniowy potok **batch ELT**, który pobiera wyniki i statystyki zaawansowane (xG)
z **wielu europejskich lig**, ładuje je do hurtowni, modeluje w gwiazdę i serwuje
analizy: **które drużyny i którzy zawodnicy przewyższają / zawodzą względem swojego
xG — i jak wypadają w porównaniu między ligami?**

Projekt ma dwóch odbiorców: **rekrutera** (kompletny warsztat data engineera) oraz
**autora** — realne narzędzie do nauki statystyki i lepszego rozumienia piłki, ze
szczególnym skupieniem na **Ekstraklasie**. Stąd rozbudowana warstwa analityczna
(notebooki + interaktywna aplikacja Streamlit), a nie pojedynczy dashboard. Pełne
uzasadnienia decyzji, źródła danych i fazy budowy opisuje [`plan.md`](./plan.md).

**Zakres danych:** 12 lig na wynikach (football-data.org) · top-5 lig z xG
(Understat) · Ekstraklasa osobno (API-Football + odpowiedzialny scraping FBref).

## Architektura

```
football-data.org (12 lig) ─┐
Understat (xG, top-5) ───────┤
API-Football (Ekstraklasa) ──┤─▶ Python (requests + pydantic) ─▶ GCS raw (bronze)
FBref (xG Ekstraklasy) ──────┘   (scraping; dane prywatne)          │
                                                                    ▼
                          BigQuery: raw ─▶ dbt staging (silver) ─▶ dbt marts (gold)
                                                                    │
                                              ┌─────────────────────┼─────────────────┐
                                              ▼                     ▼                 ▼
                                        Notebooki (statystyka)  Streamlit (appka)  Looker Studio
```

Orkiestracja: **Airflow** · Provisioning: **Terraform** · CI: **GitHub Actions**.

## Stack

| Warstwa | Technologia |
| :--- | :--- |
| Ingestion | Python, requests, pydantic |
| Data lake (raw) | Google Cloud Storage |
| Hurtownia | BigQuery |
| Transformacje + testy | dbt Core |
| Orkiestracja | Apache Airflow |
| IaC | Terraform |
| CI/CD | GitHub Actions |
| Jakość kodu | uv, ruff, pytest, pre-commit |
| Analityka + nauka | Jupyter, pandas, plotly |
| Aplikacja | Streamlit |
| Dashboard-wizytówka | Looker Studio |

## Szybki start (dev)

```bash
uv sync                        # środowisko + zależności
cp .env.example .env           # uzupełnij sekretami (.env nie trafia do repo)
uv run pre-commit install      # hooki na git commit
uv run pre-commit run --all-files
uv run pytest
```

## Struktura repo

```
ingestion/   # pobieranie danych do warstwy raw (pydantic, klient GCS, scrapery)
dags/        # DAG-i Airflow (faza 7)
dbt/         # modele staging/marts, seedy, snapshots, testy
notebooks/   # eksploracja + nauka statystyki (faza 6)
app/         # aplikacja Streamlit (faza 6)
terraform/   # bucket GCS, datasety BigQuery, service account (faza 8)
tests/       # pytest + fixtures
data/        # lokalny cache/eksport — w .gitignore (dane FBref nigdy do repo)
```

## Status

Budowa fazami wg [`plan.md` §7](./plan.md) — od cienkiego pionu end-to-end
w stronę pogłębiania. **Aktualnie: Faza 0 — fundamenty repo.**
