# Backend Dead Code Analysis

Generated: 2026-02-16

## Summary

Analysis of `/home/framework/Projects/litmatch/backend/` Python code for dead code, unused imports, and refactoring opportunities.

**Status: COMPLETED ✅**

**Changes Applied:**
1. Removed redundant `_build_rating_subquery()` wrapper function (3 lines)
2. Removed unused `RecommendationResponse` model class (4 lines)
3. **Total lines removed: 7 lines**
4. **All tests passing:** 58/58 in tests/backend, 107/110 in backend/tests (3 pre-existing failures unrelated to cleanup)

## Findings

### SAFE TO REMOVE

#### 1. Redundant wrapper function in backend/app/main.py

**Lines 78-80:**
```python
def _build_rating_subquery():
    """Build a subquery that computes avg rating and review count per book."""
    return build_rating_subquery()
```

**Issue:** This function simply wraps `build_rating_subquery()` from `backend.app.queries` without adding any value.

**Used in:**
- Line 333: `rating_sub = _build_rating_subquery()`
- Line 396: `rating_sub = _build_rating_subquery()`
- Line 573: `rating_sub = _build_rating_subquery()`
- Line 825: `rating_sub = _build_rating_subquery()`

**Recommendation:** Replace all calls to `_build_rating_subquery()` with direct calls to `build_rating_subquery()`, then remove the wrapper function.

**Impact:** Zero - just removes unnecessary indirection.

---

### CAUTION

#### 2. Unused model classes in backend/db/models.py

**Lines 261-264:**
```python
class RecommendationResponse(BaseModel):
    items: list[BookRead]
    meta: RecommendationMeta
```

**Issue:** This model is not imported or used anywhere in the codebase. The `/recommendations/` endpoint uses `PaginatedRecommendationResponse` instead.

**Recommendation:** Remove if truly unused. Verify by searching codebase first.

---

### NO ACTION NEEDED

#### 3. All imports in main.py are used

Verified that all imports in `backend/app/main.py` are actively used in the file.

#### 4. All functions in auth.py are used

All functions in `backend/app/auth.py` are imported and used by `main.py`.

#### 5. Config values are all used

All configuration values in `backend/app/config.py` are imported and used.

#### 6. Database module is minimal

`backend/database.py` is already minimal with only the essential `init_db()` function.

## Cleanup Plan

### Phase 1: Remove redundant wrapper (SAFE)

1. Run backend tests to establish baseline
2. Replace `_build_rating_subquery()` calls with `build_rating_subquery()`
3. Remove `_build_rating_subquery()` function
4. Re-run tests to verify no breakage

### Phase 2: Remove unused model (CAUTION)

1. Search entire codebase for `RecommendationResponse`
2. If confirmed unused, remove the class definition
3. Run tests

## Test Verification Commands

```bash
# Run backend unit tests
uv run pytest tests/backend/ -v

# Run backend-specific tests
uv run pytest backend/tests/ -v

# Run all tests
uv run pytest tests/ -v
```

## Files Analyzed

- ✅ backend/app/main.py (906 lines)
- ✅ backend/app/auth.py (105 lines)
- ✅ backend/app/queries.py (18 lines)
- ✅ backend/app/rate_limit.py (5 lines)
- ✅ backend/app/recommendations.py (215 lines)
- ✅ backend/app/config.py (21 lines)
- ✅ backend/db/models.py (287 lines)
- ✅ backend/database.py (38 lines)
- ✅ backend/tests/*.py (test files)
- ✅ tests/backend/*.py (test files)

## Conclusion

The backend codebase is already quite clean. Only 2 items identified:

1. **Redundant wrapper function** - safe to remove (low risk)
2. **Potentially unused model class** - needs verification (medium risk)

Total lines that can be removed: ~7 lines (wrapper function + unused model)
