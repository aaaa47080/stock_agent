# Docker & Ephemeral Storage Optimization Design

**Date:** 2026-03-16
**Status:** Approved
**Platform:** Zeabur (Kubernetes-managed PaaS)

## Problem

Kubernetes node was evicted due to low ephemeral-storage. Root causes:

1. **Oversized Docker image** — `playwright` and `trafilatura` are included in production `requirements.txt` but are never imported by the main API (`api/` or `core/`). They are only used by offline scripts in `web_crawler/` and `tests/`.
2. **Runtime cache written to container writable layer** — `appuser` HOME is `/app`, so packages like `yfinance` write their cache to `/app/.cache/`, which lives in the container's writable layer and counts against node ephemeral-storage. `/tmp` is already mounted as an emptyDir volume (does not count against node disk).

## Non-Goals

- Do not remove `pandas`, `numpy`, `pandas-ta`, `yfinance` — used by stock/forex/commodity API routers.
- Do not remove `langchain*`, `langgraph*` — used by `core/agents/`.
- Do not change multi-stage Dockerfile structure — already correct.
- Do not change `PYTHONDONTWRITEBYTECODE=1` — already set correctly.

## Changes

### 1. Split requirements

Create `requirements-dev.txt` for packages only needed outside production, using the same version pins currently in `requirements.txt`:

```
playwright==1.58.0
trafilatura==2.0.0
```

Remove those two entries from `requirements.txt`.

**CI note:** Any CI job that runs `web_crawler/` scripts or Playwright-based tests must add `pip install -r requirements-dev.txt` before those steps. The main API test suite does not import either package, so it is unaffected.

**Note on `beautifulsoup4`:** It has zero direct imports in `api/` or `core/`, but `yfinance` pulls it in as a transitive dependency. Removing it from `requirements.txt` has no effect on image size — `pip` will still install it via `yfinance`. Leave it in `requirements.txt` as a declared transitive dep.

**Expected savings:** ~170–200 MB, almost entirely from removing `playwright` (~170–200 MB). `trafilatura` saves only ~2–5 MB.

### 2. Dockerfile — redirect runtime caches to /tmp

Add ENV vars to the runtime stage so all package caches write to `/tmp` (emptyDir, not node disk):

```dockerfile
ENV XDG_CACHE_HOME=/tmp \
    MPLCONFIGDIR=/tmp \
    NUMBA_CACHE_DIR=/tmp
```

- `XDG_CACHE_HOME=/tmp` — redirects generic cache directory used by `yfinance` and other tools (e.g., `~/.cache/yfinance/`).
- `NUMBA_CACHE_DIR=/tmp` — `pandas-ta` introduces `numba` as a transitive dependency; `numba` writes JIT compilation cache on first use. Without this, cache writes land in `/app/.cache/numba/`.
- `MPLCONFIGDIR=/tmp` — precautionary; `matplotlib` is not a direct production dependency but may be pulled in transitively. Harmless to set.

Place these alongside the existing `PIP_NO_CACHE_DIR` block in the runtime stage.

### 3. Regenerate lock file

After modifying `requirements.txt`, regenerate `requirements.lock.txt` so Zeabur uses the updated pinned versions.

## Files Changed

| File | Change |
|------|--------|
| `requirements.txt` | Remove `playwright`, `trafilatura` |
| `requirements-dev.txt` | Create; add `playwright`, `trafilatura` |
| `Dockerfile` | Add `XDG_CACHE_HOME`, `MPLCONFIGDIR`, `NUMBA_CACHE_DIR` to runtime ENV block |
| `requirements.lock.txt` | Regenerate after `requirements.txt` change |

## Verification

After deploying the new image:
1. **Image size** — check Zeabur build log; compressed image size should decrease by ~170–200 MB.
2. **No import errors** — API startup logs show no `ModuleNotFoundError` (playwright/trafilatura are not imported by the API).
3. **Cache redirect** — after the container is running, exec in and confirm `/app/.cache/` is absent or empty: `docker exec <container> ls /app/.cache/ 2>&1 || echo "no cache dir"`. On Zeabur, check the ephemeral-storage usage graph; it should stay flat over time instead of growing.
