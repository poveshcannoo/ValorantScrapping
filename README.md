# 🎯 Valorant Match & Pre-Match Odds Scraper

An automated data collection pipeline for **Valorant competitive matches**, designed to harvest pre-match odds and map-by-map round scores from [VLR.gg](https://www.vlr.gg/).

---

## 🚀 Features

* **Automated Data Scraping:** Runs on a continuous schedule via GitHub Actions to collect match data around the clock.
* **Strict Pre-Match Odds Filtering:** Distinguishes between pre-match and live odds, strictly logging true pre-match lines.
* **Geo-Blocking Bypass:** Dynamically fetches European proxies to bypass regional cloud IP restrictions on VLR.gg.
* **Queue Management System:** Uses a lightweight JSON queue (`pending_matches.json`) to track upcoming games and automatically backfills finished map scores into `vlr_matches_with_odds.csv`.

---

## 📁 Repository Structure

```text
├── .github/
│   └── workflows/
│       └── scrape.yml              # Scheduled GitHub Actions workflow
├── vlr_live_scraper.py             # Main scraper and data harvester script
├── pending_matches.json            # Active queue tracking upcoming matches
├── vlr_matches_with_odds.csv       # Output CSV dataset containing match results
├── requirements.txt                # Python dependencies
└── README.md                       # Project documentation
