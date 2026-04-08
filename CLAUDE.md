# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Spanish-language inventory monitoring system for Odoo storefronts. A Python bot scrapes stock data and pushes it to JSONBin.io; a vanilla JS dashboard reads from JSONBin.io to display real-time status. Alerts are sent via Twilio WhatsApp API.

## Running the Bot

```bash
# Install dependencies (no requirements.txt exists)
pip install requests beautifulsoup4 twilio schedule

# Run continuously (3 scheduled checks daily at 08:00, 13:00, 18:00)
python monitor_stock.py

# Single test run
python monitor_stock.py --test
```

## Running the Dashboard

Open `index.html` directly in a browser, or deploy to Vercel (configured in `vercel.json`). No build step needed — pure HTML/CSS/JS.

## Architecture

The system has two independent components synchronized through JSONBin.io:

**Backend** (`monitor_stock.py`):
- Scrapes `vauxoo-psadurango.odoo.com/shop` with BeautifulSoup for stock data per SKU
- Classifies each product as `ok`, `warn` (low stock), or `danger` (out of stock)
- Sends WhatsApp alerts via Twilio when issues are detected
- Writes `estado_global` JSON state to JSONBin.io after each review

**Frontend** (`index.html`):
- Single-file SPA (~995 lines); all styles, logic, and markup inline
- Polls JSONBin.io every 60 seconds and renders metrics, product cards, and alert log
- Saves configuration (JSONBin credentials, product list, review times) to `localStorage`
- Has an "Export" tab that generates Python config code for the user to paste into `monitor_stock.py`

**Shared state schema (JSONBin)**:
```json
{
  "productos": [{"nombre": "", "sku": "", "stock": 0, "estado": "ok|warn|danger", "mensaje": ""}],
  "ultima_revision": "DD/MM/YYYY HH:MM",
  "revisiones_hoy": 0,
  "alertas": [{"tipo": "", "producto": "", "mensaje": "", "hora": "DD/MM HH:MM"}]
}
```

## Configuration

All credentials are hardcoded at the top of `monitor_stock.py`:
- `TWILIO_*`: Account SID, Auth Token, WhatsApp from/to numbers
- `JSONBIN_BIN_ID` / `JSONBIN_API_KEY`: Cloud JSON storage
- `PRODUCTOS`: List of `{"nombre", "sku", "min_stock"}` dicts
- `HORA_REVISION_1/2/3`: Scheduled check times

The dashboard's configuration panel generates a Python snippet (`generateExport()`) that the user manually pastes into the bot script — this is the intended workflow for updating bot configuration via the UI.

## Deployment

- **Dashboard**: Vercel static hosting (`vercel.json` already configured)
- **Bot**: PythonAnywhere or any persistent Python host (runs as a continuous process)
- **Data layer**: JSONBin.io free tier (single BIN stores all state)
