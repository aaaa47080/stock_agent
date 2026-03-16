# Docker Ephemeral Storage Optimization Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce production Docker image size by removing dev-only packages and redirect runtime caches to `/tmp` to prevent ephemeral storage exhaustion on Kubernetes nodes.

**Architecture:** Remove `playwright` and `trafilatura` from `requirements.txt` into a new `requirements-dev.txt`; add `XDG_CACHE_HOME`, `MPLCONFIGDIR`, and `NUMBA_CACHE_DIR` env vars to the Dockerfile runtime stage so package caches write to the emptyDir-mounted `/tmp` instead of the container writable layer.

**Tech Stack:** Python 3.13, Docker multi-stage build, pip-compile (`pip-tools`), Zeabur (Kubernetes PaaS)

**Spec:** `docs/superpowers/specs/2026-03-16-docker-ephemeral-storage-optimization-design.md`

---

## Chunk 1: Requirements split + Dockerfile cache redirect

### File Map

| Action | File | Change |
|--------|------|--------|
| Modify | `requirements.txt` | Remove `playwright==1.58.0`, `trafilatura==2.0.0` |
| Create | `requirements-dev.txt` | New file with dev-only packages |
| Modify | `Dockerfile` | Add 3 env vars to runtime stage ENV block |
| Regenerate | `requirements.lock.txt` | Re-run `pip-compile` after requirements.txt change |

---

### Task 1: Remove dev-only packages from requirements.txt

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Verify the lines to remove**

  Confirm these exact lines appear in `requirements.txt`:
  ```
  trafilatura==2.0.0
  playwright==1.58.0
  ```

  Run:
  ```bash
  grep -n "trafilatura\|playwright" requirements.txt
  ```
  Expected output:
  ```
  58:trafilatura==2.0.0
  66:playwright==1.58.0
  ```

- [ ] **Step 2: Remove trafilatura and its section comment**

  In `requirements.txt`, delete the `trafilatura==2.0.0` line from the `# === News / Search ===` section.

  The section currently reads:
  ```
  # === News / Search ===
  duckduckgo-search==8.1.1
  trafilatura==2.0.0
  ```

  After edit it should read:
  ```
  # === News / Search ===
  duckduckgo-search==8.1.1
  ```

- [ ] **Step 3: Remove playwright and its section**

  In `requirements.txt`, delete both the `# === Web / Scraping ===` comment and `playwright==1.58.0` line entirely (the section becomes empty).

  The section currently reads:
  ```
  # === Web / Scraping ===
  playwright==1.58.0
  ```

  After edit that entire block should be gone.

- [ ] **Step 4: Verify requirements.txt no longer contains playwright or trafilatura**

  Run:
  ```bash
  grep -n "trafilatura\|playwright" requirements.txt
  ```
  Expected: no output (exit code 1).

---

### Task 2: Create requirements-dev.txt

**Files:**
- Create: `requirements-dev.txt`

- [ ] **Step 1: Create the file**

  Create `requirements-dev.txt` at the project root with this exact content:
  ```
  # Dev-only / offline scripts — NOT installed in the production Docker image
  # Install with: pip install -r requirements-dev.txt
  playwright==1.58.0
  trafilatura==2.0.0
  ```

- [ ] **Step 2: Verify the file exists and contains the right pins**

  Run:
  ```bash
  cat requirements-dev.txt
  ```
  Expected: the two packages with the exact versions above.

---

### Task 3: Add runtime cache redirect env vars to Dockerfile

**Files:**
- Modify: `Dockerfile`

- [ ] **Step 1: Locate the existing ENV block in the runtime stage**

  The runtime stage (second `FROM python:3.13-slim`) currently has:
  ```dockerfile
  ENV PIP_NO_CACHE_DIR=1 \
      PIP_DISABLE_PIP_VERSION_CHECK=1 \
      PYTHONDONTWRITEBYTECODE=1 \
      PYTHONUNBUFFERED=1
  ```
  This is at lines 24–27. Note: the builder stage (lines 3–6) has an identical ENV block — leave that one unchanged. Only modify the runtime stage block.

- [ ] **Step 2: Extend the ENV block with cache redirect vars**

  Replace that ENV block with:
  ```dockerfile
  ENV PIP_NO_CACHE_DIR=1 \
      PIP_DISABLE_PIP_VERSION_CHECK=1 \
      PYTHONDONTWRITEBYTECODE=1 \
      PYTHONUNBUFFERED=1 \
      XDG_CACHE_HOME=/tmp \
      MPLCONFIGDIR=/tmp \
      NUMBA_CACHE_DIR=/tmp
  ```

  - `XDG_CACHE_HOME=/tmp` — redirects `yfinance` and other tools away from `~/.cache/` (which resolves to `/app/.cache/` for appuser).
  - `NUMBA_CACHE_DIR=/tmp` — `pandas-ta` pulls in `numba` transitively; numba writes JIT cache on first use.
  - `MPLCONFIGDIR=/tmp` — precautionary for any transitive matplotlib usage.

- [ ] **Step 3: Verify the ENV block in the final Dockerfile**

  Run:
  ```bash
  grep -A 10 "^ENV PIP_NO_CACHE_DIR" Dockerfile | tail -1
  ```
  Expected: `    NUMBA_CACHE_DIR=/tmp` (the last line of the block).

---

### Task 4: Regenerate requirements.lock.txt

**Files:**
- Regenerate: `requirements.lock.txt`

- [ ] **Step 1: Check pip-compile is available**

  Run:
  ```bash
  pip-compile --version
  ```
  If not installed:
  ```bash
  pip install pip-tools
  ```

- [ ] **Step 2: Regenerate the lock file**

  Run the same command shown at the top of the existing `requirements.lock.txt`:
  ```bash
  pip-compile --output-file=requirements.lock.txt requirements.txt
  ```
  This will take 30–60 seconds as it resolves all transitive dependencies.

- [ ] **Step 3: Verify playwright and trafilatura are gone from lock file**

  Run:
  ```bash
  grep -i "playwright\|trafilatura" requirements.lock.txt
  ```
  Expected: no output.

- [ ] **Step 4: Verify beautifulsoup4 is still present (transitive via yfinance)**

  Run:
  ```bash
  grep "beautifulsoup4==" requirements.lock.txt
  ```
  Expected: any `beautifulsoup4==X.Y.Z` line present (exact version may differ if pip-compile resolves a newer patch).

---

### Task 5: Commit all changes

- [ ] **Step 1: Stage all changed files**

  ```bash
  git add requirements.txt requirements-dev.txt Dockerfile requirements.lock.txt
  ```

- [ ] **Step 2: Verify staged files**

  Run:
  ```bash
  git diff --cached --name-only
  ```
  Expected:
  ```
  Dockerfile
  requirements-dev.txt
  requirements.lock.txt
  requirements.txt
  ```

- [ ] **Step 3: Commit**

  ```bash
  git commit -m "$(cat <<'EOF'
  fix: remove playwright/trafilatura from prod image, redirect runtime caches to /tmp

  - Moves playwright==1.58.0 and trafilatura==2.0.0 to requirements-dev.txt
    (only used by web_crawler/ scripts, never imported by api/ or core/)
  - Adds XDG_CACHE_HOME, MPLCONFIGDIR, NUMBA_CACHE_DIR=/tmp in Dockerfile
    so yfinance/numba/etc write caches to emptyDir volume, not container writable layer
  - Regenerates requirements.lock.txt

  Fixes: node ephemeral-storage eviction on Zeabur

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
  EOF
  )"
  ```

- [ ] **Step 4: Verify commit**

  Run:
  ```bash
  git log --oneline -1
  ```
  Expected: the commit message above as the latest commit.

---

### Post-deploy verification

After pushing and Zeabur redeploys:

1. **Image size** — check Zeabur build log; compressed image size should decrease by ~170–200 MB.
2. **No import errors** — API startup logs show no `ModuleNotFoundError`.
3. **Cache redirect (runtime)** — if you have exec access to the running container, confirm `/app/.cache/` is absent or empty:
   ```bash
   docker exec <container> ls /app/.cache/ 2>&1 || echo "no cache dir — correct"
   ```
4. **Cache redirect (Zeabur)** — monitor the ephemeral-storage usage graph; it should stay flat over time instead of growing after the first few requests.
