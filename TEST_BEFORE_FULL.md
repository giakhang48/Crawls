# Before running full

Run:

```powershell
python main.py crawl-test --reset --delay 2
```

Do **not** run full unless the test shows:

- Root pages = 1
- List pages > 0
- Movie candidate pages > 0
- HTTP 200 pages > 1
- Unresolved crawl errors = 0
- RESULT: PASS

A few recovered HTTP 429 responses are acceptable if retries later succeed.
Persistent 429 errors are not acceptable for a full run.

If 429 persists, stop and retry later with:

```powershell
python main.py crawl-test --reset --delay 5
```
