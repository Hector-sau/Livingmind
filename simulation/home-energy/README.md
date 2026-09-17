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
- The result is supplied precomputed evidence. This migration intentionally does not retrain or re-evaluate the model.
- The daily-cost total includes every environment cost term. Do not infer a complete cost breakdown from the legacy chart, whose visible bars omit diesel cost while its total includes it.

## Optional research runtime

`requirements-research.txt` is intentionally separate from the App and backend requirements. It is only needed for future research reproduction, never for a demonstration build or CI.

## Provenance

`provenance/manifest.json` captures the local source snapshot, baseline Git revision and SHA-256 values of selected source files. The original source folder is not changed by this migration.
