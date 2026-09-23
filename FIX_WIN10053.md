# Fix for Windows `WinError 10053`

## What happened
The first full-crawl build used 16 crawler workers, 5,000 movie links per listing page, and a 20-second read timeout. On Windows/Python 3.14, several concurrent large listing responses could exceed the client read window. The Requests client then closed the socket while the local mirror was still writing, so the mirror printed:

`ConnectionAbortedError: [WinError 10053]`

This is a localhost transport/timeout problem, not corrupt IMDb source data.

## What v1.1 changes
- listing size: **5,000 -> 1,000** movies/page
- workers: **16 -> 8**
- read timeout: **20 -> 90 seconds**
- retries: **4 attempts/request** after timeout/connection abort
- listing DB lookup: large concurrent `OFFSET` scans replaced by indexed key-range lookup
- local TCP: enables `TCP_NODELAY`
- mirror safely catches client-aborted sockets instead of printing giant tracebacks

## What to run
Keep the existing `data/imdb_source.db` (757,298 source movies). Delete/ignore the incomplete crawler output `data/imdb.db`, then run:

```powershell
python main.py crawl-test --reset
```

Only after test ends with `RESULT: PASS`:

```powershell
python main.py crawl-full --reset
```

If Windows security/network software is still aggressive:

```powershell
python main.py crawl-full --reset --workers 4
```

The final run is accepted only when validation ends with `RESULT: PASS` and `Crawl errors: 0`.
