TensegrityOrientationHarvesterV2

Prototype harvester that normalizes orientation/time-series data into a consistent CSV and emits a provenance report (source URL/path, checksum, notes).

Usage:
- Run with Python 3.8+:
  python main.py sample_inputs
- 'sample_inputs' is a directory containing example files (CSV or JSON). The script also accepts file paths or HTTP(S) URLs if network access is available.

This prototype is local-only and avoids automated crawling or repository API calls. It's intended as a clear starting point for adding crawling, repository adapters, authentication, and richer metadata handling.