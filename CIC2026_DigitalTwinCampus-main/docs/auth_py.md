# File: auth.py
**Overview**
- **Purpose:** `EBAuthManager` handles login, token persistence, and automatic token refresh for the Empathic Building API.

**Key constants**
- **`BASE_URL`**: API base `https://eu-api.empathicbuilding.com`.
- **`TOKEN_FILE`**: Path token.json where tokens are persisted.

**`EBAuthManager` lifecycle**
- **Init:** reads `EB_EMAIL`/`EB_PASSWORD` from args or env, attempts to `_load_token()` from disk.
- **Token validity:** stores `_token` dict and `_expires_at` (epoch seconds). All checks use a 60s safety buffer.
- **Ensure valid:** `get_headers()` calls `_ensure_valid_token()` which either:
  - logs in if no token in memory, or
  - refreshes with `_refresh()` if token is near expiry, falling back to `_login()` on refresh failure.

**Network calls**
- **`_login()`**: POSTs form data to `/v1/login` with `email`/`password`. Raises `ValueError` if credentials missing. Uses `response.raise_for_status()` so HTTP errors propagate.
- **`_refresh()`**: POSTs refresh token to `/v1/token` and stores the new token on success.
- **Timeouts:** each request sets `timeout` to avoid hangs.

**Persistence**
- **`_store_token(token_data)`**: writes token to memory, computes `_expires_at`, annotates `token_data` with `_expires_at` and `_saved_at`, ensures data exists, and writes token.json.
- **`_load_token()`**: loads token file if present and still valid (now < `_expires_at - 60`); otherwise ignores it. Errors while loading are caught and printed.

**Public API**
- **`get_headers()`**: returns ready-to-use headers including `Authorization: <token_type> <access_token>` and `Accept: application/json`.
- **`force_login()`**: forces a fresh login (bypasses cached token).

**Singleton helper & CLI**
- **`get_auth(email=None, password=None)`**: returns a module-level singleton `EBAuthManager`.
- **CLI block:** When run directly, prompts for credentials and prints prepared headers (quick sanity check).
