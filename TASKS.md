# Follow-up Tasks

## Typo Fix Task
- **Issue**: The API response in `api/server.py` says "running in background," which reads like a typo/grammar mistake because it omits the article "the." This is user-facing text returned from the `/trigger` endpoint.
- **Suggested Fix**: Update the success message to read "running in the background" so user-facing text is grammatically correct.

## Bug Fix Task
- **Issue**: `agent/clients/bus_client.py` calls `.strip()` on `item.get("remarks", "")`. When the NJ Transit API returns `None` for `remarks`, calling `.strip()` raises an `AttributeError`, causing the whole schedule fetch to fail.
- **Suggested Fix**: Normalize `remarks` to an empty string before stripping (e.g., `remarks = (item.get("remarks") or "").strip()`) so the client tolerates missing remarks.

## Comment/Documentation Fix Task
- **Issue**: `agent/clients/bus_client.py` logs raw data in `get_bus_stops()` with a comment `# <== ADD THIS LINE`, which looks like leftover reviewer instructions rather than documentation of the logging behavior.
- **Suggested Fix**: Replace the comment with an explanation of why the verbose log exists (or remove it entirely) to keep comments aligned with the code's intent.

## Test Improvement Task
- **Issue**: `test.py` is not a real test; it makes a live POST to the Telegram Bot API, which will fail without credentials and is unsafe for automated runs.
- **Suggested Fix**: Replace this script with an automated unit test (e.g., using `pytest`) that validates local behavior such as message formatting without external network calls.
