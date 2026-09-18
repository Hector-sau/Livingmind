# LivingMind Home Energy Simulation

This directory preserves the team’s household-energy research as an **offline simulation**. FastAPI reads only its supplied JSON evidence; it never imports the research runtime or directly controls a LivingMind device from it.

## What is included

- A fixed 24-hour household environment: PV, wind, base load, HVAC, battery, grid trading and a diesel backup generator.
- A MATD3 research implementation and one supplied HomeEnergy actor weight.
- The supplied one-day rule-versus-MATD3 result in `data/provided-day-comparison.json`.

## What the App does with it

The LivingMind App reads the structured, supplied result through a read-only API and labels it as **offline simulation / fixed predefined day**. Its online energy advice remains `backend/app/energy/rules.py`: a transparent comfort-band and time-of-use rule. MATD3 is not loaded by the backend, is not called by an Agent, and is not a real-time device controller.

## Scope and limits

- One episode is 24 hourly decisions on one fixed predefined day.
- `agentCount` is 1. Although the code uses a MATD3 framework, this supplied run is a single-agent controller, not a multi-agent collaboration result.
- Costs use USD and temperatures use Fahrenheit in the research environment.
- The result is supplied precomputed evidence. This migration does not retrain the model. It **was** re-evaluated once in this repository (`research/reproduce_day.py`, seed 42): all eight KPIs match the supplied figure within 0.005, and the reproduced numbers are in `data/reproduced-day-comparison.json`.
- The daily-cost total includes every environment cost term. Do not infer a complete cost breakdown from the legacy chart, whose visible bars omit diesel cost while its total includes it.

## Reproducing the one-day comparison

```bash
cd simulation/home-energy
python -m venv .venv && .venv/bin/pip install -r requirements-research.txt
MPLBACKEND=Agg .venv/bin/python research/reproduce_day.py     # writes data/reproduced-day-comparison.json
```

The script imports the evaluation from `research/plot_product_demo.py` rather than copying it,
so there is no second implementation of the environment, the policies or the metrics. It loads
the supplied actor weight, runs one MATD3 day and one rule-based day, and compares each KPI with
the supplied figure (tolerance 0.01, the figure's own rounding). It never trains or overwrites a model.

## Optional research runtime

`requirements-research.txt` is intentionally separate from the App and backend requirements. It is only needed for future research reproduction, never for a demonstration build or CI.

## Provenance

`provenance/manifest.json` captures the local source snapshot, baseline Git revision and SHA-256 values of selected source files. The original source folder is not changed by this migration.
