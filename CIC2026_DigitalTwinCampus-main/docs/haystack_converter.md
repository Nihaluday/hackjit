# File: haystack_converter.py

**Overview**
- **Purpose**: Convert raw Empathic Building sensor records into Project Haystack (Hayson) entities, using a local `space_mapping.json` to attach IFC space references when the API doesn't provide them.

**Space matching**
- **Loader**: `load_space_mapping()` loads space_mapping.json or returns `[]` with a warning.
- **Match strategy**: `_match_space(sensor, spaces)` tries, in order:
  - exact match sensor['space_id'] → space['space_number']
  - exact match sensor['name'] → space['space_number']
  - exact match sensor['vendor_id'] → space['space_number']
  - fuzzy: sensor name fragment (length>3) contained in space['space_name'] (case-insensitive)
- **Outcome**: returns the matched `space` dict or `None`.

**Type mapping & value extraction**
- **`_TYPE_MAP`**: maps EB `type` strings (e.g., `"temperature"`, `"co2"`, `"occupancy"`) to Haystack tag fragments, kind, and unit.
- **`_get_cur_val(sensor, s_type)`**: extracts the current measurement from `sensor["last_measurement"]`; handles occupancy (checks `used > 0`) and otherwise returns `last["value"]`.

**Transform logic**
- **`transform_sensor(sensor, space_mapping)`**:
  - Builds a Haystack-style entity dict with keys: `id` (prefix `r:`), `dis`, `point`, `sensor`, `siteRef` (fixed `r:Myllypuro_Campus`), and EB metadata (`eb_id`, `eb_type`, `eb_vendor`, `eb_vendor_id`).
  - Adds space info when `_match_space` finds a match: `spaceRef` (`r:{space_guid|space_number}`), `floorRef`, and `dis_space`. If no match, sets `"unlocated": "m:"`.
  - Merges semantic tags from `_TYPE_MAP`.
  - If a current value exists, adds `curVal`, `cur`, and `curStatus`.
  - Copies a timestamp into `lastUpdate` from `last_measurement.measured_at` or `timestamp` if present.
  - Returns the single Haystack entity dict.

**Batch conversion & diagnostics**
- **`convert_sensors(raw_sensors, space_mapping)`**: maps `transform_sensor` across the list and returns the Haystack model list.
- **`print_summary(haystack_model)`**: prints total count, located vs unlocated counts, and a by-type breakdown.

**Standalone usage**
- The `__main__` block can convert the newest `raw_metadata_loc*.json` in data to a Haystack JSON for quick testing.

**Notes / Suggestions**
- **Space mapping required**: Without space_mapping.json, many sensors will be `unlocated`.
- **Fuzzy matching**: current fuzzy rule is simple substring matching; consider using tokenization or a string-similarity library for better matches.
- **Timestamps**: converter copies whatever timestamp the API provides; normalizing to ISO/UTC could improve consistency.
- **Extensibility**: add configurable `siteRef` or allow mapping overrides per vendor/type if needed.
