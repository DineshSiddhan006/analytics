# Warehouse Business Analytics Pipeline

## Flow
1. Connect directly to the configured Microsoft Fabric warehouse.
2. Load the complete selected table (the row cap is a safety check; data is never silently truncated).
3. Profile all rows and columns, then ask the configured LLM for fresh, executable business-analytics proposals. Unsupported predictions, correlations, lags, and non-temporal line charts are rejected; legacy saved plans using them move to rejected history.
4. Merge the new proposals with JSON-persisted approved analytics. Previously rejected analytics are suppressed.
5. On every run, review each analysis as a plain-language description and chart choice. Add further analyses in plain language. Nothing is computed until **Proceed to dashboard**.
6. Execute approved analytics and render a Power BI-inspired, light-theme dashboard in static PNG pages of up to six readable visuals. Compact visual rows can show three cards; dense charts use two wider cards, while a single visual fills its row. The dashboard uses a soft gray canvas, white 12px-radius cards with 1px borders and 16px gaps, bundled Outfit typography (400/500/600), and the exact style-guide palette. Positive-only plots start at zero; histograms do not create negative bins for nonnegative data. Product, station, route, type, and other coded values use `data/value_mappings.json`, supplemented with unambiguous warehouse dimension labels. Dashboard output contains no interactive charts, tables, or explanatory text outside the images.
7. Ask **Cargo Intelligence** questions about the current dataset profile, analytics under review, and dashboard results from the bottom-right chat input.

## Run

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

The supplied `.env` is retained. Authentication is performed against the warehouse; connection/authentication/LLM errors are shown and are not redirected to local files or sample data.

## Persistence

One JSON file per warehouse table is stored under `data/plans/` by default. It contains `approved` (including edits) and `rejected` analytics definitions only. Charts and computed results are not persisted. Mount `data/plans/` as a persistent volume when deploying in a container. The editable value-to-label dictionary is `data/value_mappings.json`; set `VALUE_MAPPINGS_PATH` to use a mounted copy. It is reloaded during each planning run.

## Project structure

```text
analytics_executor/
├── app.py
├── config.py
├── fabric_warehouse.py
├── llm_client.py
├── bi_pipeline/
│   ├── common.py
│   ├── data.py
│   ├── specs.py
│   ├── executor.py
│   ├── charts.py
│   ├── llm.py
│   ├── assistant.py
│   ├── store.py
│   ├── review.py
│   ├── results.py
│   ├── service.py
│   └── container.py
├── ui/
│   ├── session.py
│   ├── review.py
│   ├── dashboard.py
│   ├── assistant.py
│   └── styles.py
├── tests/
│   ├── test_store.py
│   ├── test_specs.py
│   ├── test_review.py
│   ├── test_assistant.py
│   └── test_no_fallback_contract.py
└── data/plans/
```
