# File data_collector.py
**Overview**
- **File**: collector.py  
- **Purpose**: A small long-running service that polls the EB API, converts sensor data to a Haystack model, and writes both a stable "latest" file (for Blender) and optional timestamped history.

**Key components**

- **Imports & dependencies**: uses `get_auth` (`services.auth`), `EBApiClient` (`services.eb_api`), and `load_space_mapping`/`convert_sensors`/`print_summary` (`services.haystack_converter`). These provide auth, API access, and the conversion pipeline.
- **Configuration**: top-level constants (`DATA_DIR`, `LATEST_RAW_FILE`, `LATEST_HAYSTACK`, `TARGET_LOCATION`, `POLL_INTERVAL_SEC`, `KEEP_HISTORY`) control output paths, polling interval, target campus, and whether to keep history.
- **Logging**: configured with `logging.basicConfig` and logger `log`.

**`DataCollector` class**

- **`__init__(self, email=None, password=None)`**:
  - Ensures the `data/` directory exists.
  - Creates auth via `get_auth`, constructs `EBApiClient`, loads space mapping.
  - Initializes `org_id` and `loc_id` to `None` (resolved on first run).

- **`resolve_location(self)`**:
  - Calls `self.client.find_location(TARGET_LOCATION)` to look up the campus/location and stores `org_id` and `loc_id`.

- **`fetch_once(self) -> bool`**:
  - Ensures `org_id`/`loc_id` are resolved.
  - Calls `self.client.get_sensors(org_id, loc_id)` to fetch raw sensor list.
  - Converts raw sensors to Haystack model via `convert_sensors`.
  - Calls `print_summary` to log a summary.
  - Saves data with `self._save(...)`.
  - Returns `True` on success; on any exception logs an error and returns `False` leaving previous files untouched.

- **`_save(self, raw, haystack)`**:
  - Updates the two stable "latest" files (`raw_latest.json`, `haystack_latest.json`) used by Blender.
  - If `KEEP_HISTORY` is True, also writes timestamped `raw_metadata_loc{loc}_{timestamp}.json` and `haystack_model_loc{loc}_{timestamp}.json`.

- **`_write_json(path: Path, data)` (static)**:
  - Ensures parent directory exists.
  - Writes to a temporary file (`.tmp`) then atomically `replace()`s it to the final path — prevents Blender reading partially-written files.

- **`run(self)`**:
  - Main polling loop: repeatedly calls `fetch_once()` and sleeps `POLL_INTERVAL_SEC` seconds. Logs startup info and next fetch times. Handles Ctrl-C in the entry point.

**Entry point**

- When run as `__main__`, prompts for `EB_EMAIL`/`EB_PASSWORD` (or reads from env `EB_EMAIL`/`EB_PASSWORD`), instantiates `DataCollector`, and calls `run()`; KeyboardInterrupt is caught to log clean stop.

**Behavioral / operational notes**

- **Resilience**: token refresh handled by `EBAuthManager` (in `auth`); on fetch failure the code logs and preserves previous files so Blender keeps working.
- **Atomic writes**: `_write_json` writes to `.tmp` then replaces the target atomically on most OSes.
- **Configuration points**: change `TARGET_LOCATION`, `POLL_INTERVAL_SEC`, `KEEP_HISTORY`, or data paths at top of file.
- **Integration points to inspect**: `services/eb_api.EBApiClient` (for `find_location` and `get_sensors`) and `services.haystack_converter` (for mapping and conversion) — these determine the shape of `raw_sensors` and `haystack` that get saved.

