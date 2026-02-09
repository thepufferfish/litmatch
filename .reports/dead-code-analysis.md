# Dead Code Analysis Report

**Date:** 2026-02-08
**Branch:** dev
**Commit:** 56c2680

---

## Summary

| Category | SAFE | CAUTION | DANGER | Total |
|----------|------|---------|--------|-------|
| Unused Files | 2 | 1 | 0 | 3 |
| Unused Imports | 3 | 0 | 0 | 3 |
| Unused Classes/Functions | 1 | 0 | 0 | 1 |
| Unused Dependencies (Python) | 1 | 1 | 0 | 2 |
| Unused Dependencies (Frontend) | 0 | 0 | 0 | 0 |
| Unused Exports (Frontend) | 0 | 0 | 0 | 0 |

---

## SAFE TO REMOVE

### 1. Legacy File: `src/litmatch/defs/assets_legacy.py`

- **Status:** SAFE
- **Reason:** Marked "deprecated" at line 15. Not imported by any other file. Replaced by modular assets in `assets/` directory. Only consumer of `pandas` dependency.
- **Action:** Delete entire file.

### 2. Unused Scrapy Item: `scraper/bookmarks/items.py`

- **Status:** SAFE
- **Reason:** `BookmarksItem` class has no fields defined (just `pass`). Spider yields plain dicts, not Scrapy Items. Never imported or instantiated anywhere.
- **Action:** Delete entire file.

### 3. Unused Scrapy Pipeline: `scraper/bookmarks/pipelines.py`

- **Status:** SAFE
- **Reason:** `BookmarksPipeline` is a no-op stub (just returns item). `ITEM_PIPELINES` is commented out in `settings.py` (lines 84-86). `ItemAdapter` import is unused.
- **Action:** Delete entire file.

### 4. Unused Import: `pgvector.sqlalchemy.Vector` in `backend/db/models.py:7`

- **Status:** SAFE
- **Reason:** `Vector` is imported but never used in any column definition. No vector columns exist in the schema.
- **Action:** Remove import line 7.

### 5. Unused Import: `is_item, ItemAdapter` in `scraper/bookmarks/middlewares.py:9`

- **Status:** SAFE
- **Reason:** Neither `is_item` nor `ItemAdapter` are referenced anywhere in the file.
- **Action:** Remove import line 9.

### 6. Redundant Dependency: `psycopg2` in `pyproject.toml`

- **Status:** SAFE
- **Reason:** Both `psycopg2>=2.9.11` and `psycopg2-binary>=2.9.11` are listed. They conflict when installed together. `psycopg2-binary` is the preferred choice for deployment.
- **Action:** Remove `psycopg2>=2.9.11`, keep `psycopg2-binary>=2.9.11`.

---

## CAUTION (Keep for Now)

### 7. Placeholder Resource: `src/litmatch/defs/resources/scrapyd.py`

- **Status:** CAUTION
- **Reason:** Phase 2 placeholder. Not imported or registered in `definitions.py`. Minimal cost to keep. Remove when Phase 2 is decided.
- **Impact:** None (18 lines, never loaded).

### 8. Dependency: `pandas>=2.3.3` in `pyproject.toml`

- **Status:** CAUTION
- **Reason:** Only used by `assets_legacy.py`. After that file is removed, `pandas` is unused. However, it may be useful for future data analysis work or the recommender module.
- **Action:** Remove after confirming `assets_legacy.py` deletion. Can always re-add later.

### 9. Spider Middleware Stub: `BookmarksSpiderMiddleware` in `middlewares.py:12-56`

- **Status:** CAUTION
- **Reason:** `SPIDER_MIDDLEWARES` is commented out in settings.py (lines 54-56), so this class is never loaded. However, `BookmarksDownloaderMiddleware` (lines 59-111) in the same file IS active (settings.py line 61). Cannot delete the file.
- **Action:** Could remove `BookmarksSpiderMiddleware` class only, keeping `BookmarksDownloaderMiddleware`.

---

## DANGER (Do NOT Remove)

### Active Components Verified

- `BookmarksDownloaderMiddleware` (middlewares.py:59-111) - **ACTIVE** in settings.py line 61
- `proxies.py` (`create_proxy_list`) - **ACTIVE**, imported in settings.py line 11
- All Dagster utility functions - **ACTIVE**, used by assets
- All backend auth functions - **ACTIVE**, used by main.py endpoints
- All backend models - **ACTIVE**, used by endpoints and ETL
- All frontend hooks, components, pages - **ACTIVE**, all imported
- All frontend types - **ACTIVE** (used as nested types in Book/Review interfaces)
- `pgvector` dependency - **KEEP** for database extension setup in `backend/database.py`
- `react-hot-toast`, `react-router`, `@tanstack/react-query` - **ACTIVE**

---

## Frontend Analysis

The frontend codebase is clean:
- **0 unused files** - all 38 source files are imported
- **0 unused npm dependencies** - all packages actively used
- **0 unused CSS classes** - Tailwind + custom classes all referenced
- **0 dead exports** - all type exports used (some as nested types)

---

## Proposed Deletion Order

1. Remove `Vector` import from `backend/db/models.py` (1 line)
2. Remove `is_item, ItemAdapter` import from `scraper/bookmarks/middlewares.py` (1 line)
3. Delete `scraper/bookmarks/items.py` (entire file)
4. Delete `scraper/bookmarks/pipelines.py` (entire file)
5. Delete `src/litmatch/defs/assets_legacy.py` (entire file)
6. Remove `BookmarksSpiderMiddleware` from `scraper/bookmarks/middlewares.py` (class + unused `signals` import)
7. Remove `psycopg2` from `pyproject.toml` (keep `psycopg2-binary`)
8. Remove `pandas` from `pyproject.toml` (after step 5)

Each step will be verified by running the test suite before and after.
