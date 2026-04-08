# CLAUDE.md
This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
LaksAtlas is a salmon farming transparency dashboard for Norway. It visualizes fish health data (sea lice, disease outbreaks, escapes) sourced primarily from the Barentswatch Fishhealth API, with additional historical context and validation from official Excel datasets and Fiskehelserapporten (Veterinary Institute) reports.

The goal is to provide a clear, interactive, and visually compelling overview of Norwegian aquaculture health trends over time.

## Data Pipeline
The project uses two Python scripts to fetch and structure API data:

# Fetch current week's locality data (lice counts, disease status per farm)
python scripts/fetch_data.py
# Output: data/localities.json, data/summary.json

# Fetch historical yearly health summaries (2012–present)
python scripts/fetch_health_history.py
# Output: data/health_history.json

Both scripts read credentials from .env in the project root:

CLIENT_ID=...
CLIENT_SECRET=...

The Barentswatch API uses OAuth2 client_credentials flow at:
https://id.barentswatch.no/connect/token

- Lice data is reported weekly
- Scripts target the most recently completed week
- Historical endpoints are used for yearly aggregates

## Site Structure
The site is fully static (no framework, no build step). All files are in site/ and can be opened directly in a browser.

Core pages:

- site/index.html  
  Main landing page (currently represents year 2024).  
  This should always reflect the most recent complete dataset.

- site/2020.html, site/2021.html, site/2022.html, site/2023.html  
  Individual yearly detail pages.

- site/map.html  
  Interactive map showing farm locations, lice levels, and disease presence.

- site/comparison.html (planned)  
  Will allow users to compare multiple years across key metrics.

## Year Handling Logic
- index.html always represents the latest fully available dataset (currently 2024)
- New year pages (e.g. 2025.html) should only be created when structured data is available (API or XLSX)
- If only PDF reports exist (e.g. Vet Institute reports for 2025):
  - Do NOT use them as primary data sources for charts
  - Use them only for summaries, context, and interpretation
  - Avoid mixing incomplete years into comparisons

## Key Data Files
- data/localities.json  
  Weekly farm-level data (coordinates, lice counts, disease flags, treatments)

- data/summary.json  
  National weekly summary data

- data/health_history.json  
  Annual aggregates (2012–present), including ISA, PD, lice violations, and escape numbers

- stats/*.xlsx  
  Structured historical datasets from Fiskeridirektoratet used for validation and consistent comparisons

- stats/Fiskehelserapporten-2020.pdf to 2025.pdf  
  Annual reports from the Norwegian Veterinary Institute used for narrative context, summaries, and validation

## Source Priority
When working with data:

1. data/*.json  
   Primary source for all dashboard values and charts

2. stats/*.xlsx  
   Secondary structured reference for historical validation

3. stats/Fiskehelserapporten-*.pdf  
   Contextual source only (not for extracting numeric chart data)

Prefer JSON or XLSX for anything visualized. Use PDFs only for explanation and interpretation.

## Working with PDF Reports
Fiskehelserapporten PDFs are not machine-friendly datasets.

- Do NOT extract values for charts if structured data exists
- Use PDFs for summaries, trends, and validation
- If discrepancies occur, prefer structured data unless clearly incorrect

## Comparison Page (Future Feature)
comparison.html should:

- Allow selection of multiple years (e.g. 2020–2024)
- Compare:
  - disease counts (ISA, PD)
  - lice violations
  - escape numbers

Use data/health_history.json as the main data source.

Avoid including incomplete years (such as partial 2025 data).

## Design System
- Static HTML only (no frameworks or build tools)
- Dark neon design using CSS variables in :root
- Chart.js for visualizations
- Leaflet.js for maps

Maintain consistent styling across all pages.

## Disease Name Mapping
Barentswatch API returns Norwegian disease codes:

- INFEKSIOES_LAKSEANEMI → ISA (Infectious Salmon Anaemia)
- PANKREASSYKDOM → PD (Pancreas Disease)

## General Development Rules
- Keep everything static and lightweight
- Do not introduce frameworks or build systems
- Prioritize clarity and visual storytelling
- Ensure consistency across all pages
- Avoid duplicating logic across files
