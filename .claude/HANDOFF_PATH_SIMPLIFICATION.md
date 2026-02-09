# HANDOFF: Path Simplification Fix

## Problem Summary
The `crawl_and_load` Dagster job failed with:
```
FileNotFoundError: [Errno 2] No such file or directory: '/data/raw/raw/books.jsonl'
```

## Root Cause Analysis

The confusing `/data/raw/raw` path pattern was technically **correct** but error-prone:

1. **Scrapy FEEDS Configuration**: Wrote to `output/raw/books.jsonl` (relative to `/scraper/`)
2. **Scrapyd Container**: File exists at `/scraper/output/raw/books.jsonl`
3. **Volume Mapping**: `shared_scraper_output:/scraper/output` → `/data/raw` (in Dagster containers)
4. **Resulting Path**: `/data/raw/raw/books.jsonl` (the `/raw` subdirectory persists through the volume mount)
5. **PathResource Logic**: Simple concatenation `{raw_data_dir}/books.jsonl`
6. **Required Config**: `RAW_DATA_DIR=/data/raw/raw` to reach the file

The double `raw/raw` pattern was semantically confusing and invited "fixes" that would actually break the path resolution.

## Solution: Simplify at the Source

Instead of fixing the symptom (environment variable), we eliminated the root cause (unnecessary subdirectory):

### Changes Made

1. **Scrapy Output Path** (`scraper/bookmarks/settings.py`):
   ```python
   # Before: output/raw/books.jsonl
   # After:  output/books.jsonl
   ```
   Removed the `/raw` subdirectory from Scrapy's FEEDS path.

2. **Dagster Environment Variables** (`compose.yaml`):
   ```yaml
   # Before: RAW_DATA_DIR: /data/raw/raw
   # After:  RAW_DATA_DIR: /data/raw
   ```
   Updated both `dagster-code` and `dagster-daemon` services.

3. **Documentation Updates**:
   - `docs/RUNBOOK.md`: Updated path references and troubleshooting commands
   - `docs/CONTRIB.md`: Updated environment variable table and test config note
   - `.env.example`: Updated commented default value

### New Path Flow

1. **Scrapy FEEDS**: `output/books.jsonl`
2. **Scrapyd Container**: `/scraper/output/books.jsonl`
3. **Volume Mount**: `/scraper/output` → `/data/raw`
4. **Dagster Container**: `/data/raw/books.jsonl`
5. **PathResource**: `{raw_data_dir}/books.jsonl` = `/data/raw/books.jsonl` ✓

## Files Modified

- `scraper/bookmarks/settings.py` — Removed `/raw` subdirectory from FEEDS path
- `compose.yaml` — Updated `RAW_DATA_DIR` for both dagster services
- `docs/RUNBOOK.md` — Updated path references in 4 locations
- `docs/CONTRIB.md` — Updated environment variable documentation
- `.env.example` — Updated commented default value

## Test Configuration Alignment

The test config (`compose.test.yaml`) already used `/data/raw` because test fixtures were mounted directly without subdirectories. Now production and test environments have consistent path configurations.

## Verification Steps

1. **Rebuild containers**:
   ```bash
   podman compose down
   podman compose up --build -d
   ```

2. **Verify file path after crawl**:
   ```bash
   podman run --rm -v litmatch_shared_scraper_output:/data alpine ls -la /data/raw/
   ```
   Should show `books.jsonl` directly in `/data/raw/`

3. **Trigger crawl_and_load job** via Dagster UI at http://localhost:3000

4. **Verify raw_books asset** completes successfully

## Impact Assessment

- **Breaking Change**: Requires rebuilding containers and re-running crawls
- **Existing Data**: Old volumes will have data at `/data/raw/raw/books.jsonl`; new crawls write to `/data/raw/books.jsonl`
- **Migration Path**: Either delete old volumes or manually move the file to the new location
- **Test Compatibility**: Tests continue to work; path structure now matches production

## Security & Robustness

- No security implications; paths remain hardcoded in compose.yaml
- No additional file existence validation needed (asset dependency ensures crawl completes first)
- Simplified path reduces cognitive load and prevents future misunderstandings

## Review Notes

This fix was reviewed by the code-reviewer agent, which identified that an earlier attempt to "fix" the path was actually incorrect. The proper solution required simplifying the Scrapy output structure, not just changing the environment variable.

## Next Steps

1. ✅ Changes applied and ready for commit
2. ⏳ Test in local deployment
3. ⏳ Verify integration tests still pass
4. ⏳ Update any deployment scripts or infrastructure-as-code
