# File eb_api.py  

**Overview**
- **Purpose**: Thin wrapper around the Empathic Building REST API that resolves organizations/locations and fetches sensor data for a location.

**Constants**

- **BASE_URL**: Base API endpoint `https://eu-api.empathicbuilding.com`.  
- **TARGET_LOCATION**: Default location name `"Myllypuro"` used by `find_location` unless overridden.

**Main class**

- **`EBApiClient`**: Constructed with an `EBAuthManager` instance (`auth`) so every request uses `self.auth.get_headers()` to include a valid token.

**Key methods**

- **`get_organizations()`**:  
  - GETs `/v1/organizations` with auth headers and `timeout=15`.  
  - Calls `response.raise_for_status()` and returns parsed JSON (list of organizations).

- **`find_location(location_name: str = TARGET_LOCATION)`**:  
  - Iterates organizations and their `locations` to find a location with matching `name`.  
  - Returns a dict `{ "id", "name", "organization_id" }` on success.  
  - Raises `ValueError` with available names if not found.

- **`get_sensors(org_id, loc_id)`**:  
  - GETs `/v1/organizations/{org_id}/locations/{loc_id}/sensors` with `timeout=30`.  
  - Accepts API responses that are either a list or a wrapper dict; returns the list of sensors (tries data, `sensors`, or the list itself).

- **`get_sensor_live(org_id, loc_id, sensor_id)`**:  
  - GETs measurements for a single sensor with `params={"limit": 1}` and `timeout=15`.  
  - Returns the raw JSON response for the latest measurement.

**Error handling & behavior**

- **HTTP errors**: `response.raise_for_status()` causes HTTP errors to raise `requests.exceptions.HTTPError` (propagates to caller).  
- **Timeouts**: Explicit timeouts set per request to avoid indefinite hangs.  
- **Return shapes**: `get_sensors` normalizes different API shapes (list vs wrapper) to a list.

**Integration points**

- **Auth**: Expects `services.auth.EBAuthManager`/`get_auth` to provide `get_headers()` with a valid token.  
- **Consumers**: Used by `collector.py` (calls `find_location` and `get_sensors`) and any tooling that needs sensor metadata or live measurements.

**Notes & suggestions**

- Consider handling pagination if the API paginates sensor lists.  
- Add retries/backoff (e.g., via `tenacity`) around network calls for transient failures.  
- If location matching should be case-insensitive or fuzzy, update `find_location` accordingly.


