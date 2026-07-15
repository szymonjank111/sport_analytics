# ⚽ Football Analytics Pipeline

Tygodniowy potok **batch ELT**, który pobiera wyniki meczów i statystyki
zaawansowane (xG) z publicznych źródeł, ładuje je do hurtowni, modeluje w gwiazdę
i serwuje dashboard odpowiadający na pytanie: **które drużyny i którzy zawodnicy
przewyższają / zawodzą względem swojego xG?**

Projekt portfolio z data engineeringu — celem jest pokazanie kompletnego warsztatu
DE, a nie maksymalnej liczby technologii. Pełne uzasadnienia decyzji, model danych
i fazy budowy opisuje [`plan.md`](./plan.md).

## Architektura

```
football-data.org ─┐
                    ├─▶ Python (requests + pydantic) ─▶ GCS raw (bronze)
Understat (xG) ─────┘                                        │
                                                             ▼
                              BigQuery: raw ─▶ dbt staging (silver) ─▶ dbt marts (gold)
                                                                              │
                                                                              ▼
                                                                     Looker Studio
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
| Wizualizacja | Looker Studio |

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
ingestion/   # pobieranie danych do warstwy raw (pydantic, klient GCS)
dags/        # DAG-i Airflow (faza 5)
dbt/         # modele staging/marts, seedy, snapshots, testy
terraform/   # bucket GCS, datasety BigQuery, service account (faza 6)
tests/       # pytest + fixtures
```

## Status

Budowa fazami wg [`plan.md` §7](./plan.md) — od cienkiego pionu end-to-end
w stronę pogłębiania. **Aktualnie: Faza 0 — fundamenty repo.**
