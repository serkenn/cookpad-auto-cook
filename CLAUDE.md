# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Unofficial async Python client for the Cookpad recipe API, reverse-engineered from the iOS app. Published on PyPI as `cookpad`. Documentation and README are in Japanese.

## Commands

```bash
# Install dependencies
pip install -e .

# Install test dependencies
pip install pytest pytest-asyncio

# Run all tests
pytest tests/ -v

# Run a single test file
pytest tests/test_types.py -v

# Run a single test
pytest tests/test_types.py::test_parse_recipe -v

# Build package
python -m build
```

## Architecture

Four-module package under `cookpad/`:

- **client.py** — `Cookpad` class, async context manager wrapping `httpx.AsyncClient`. All API methods live here (search_recipes, get_recipe, get_comments, etc.). Each request adds dynamic headers (UUID, bearer token, iOS user-agent).
- **types.py** — Dataclasses (`Recipe`, `User`, `Comment`, `Ingredient`, `Step`, `Image`, `SearchResponse`, `CommentsResponse`, `UsersResponse`) and `parse_*()` functions that convert raw JSON dicts into typed objects.
- **constants.py** — API base URL (`global-api.cookpad.com/v32`), default anonymous token, default user-agent string, country/language/timezone defaults.
- **exceptions.py** — Exception hierarchy: `CookpadError` base, with `AuthenticationError` (401), `NotFoundError` (404), `RateLimitError` (429), `APIError` (other HTTP errors).

## Key Patterns

- **Async context manager**: `async with Cookpad() as client:` manages the httpx client lifecycle. Also works without `async with` (auto-creates client).
- **Two pagination styles**: Page-based (`next_page`) for recipe search, cursor-based (`next_cursor`) for comments.
- **Null-safe parsing**: All `parse_*()` functions handle missing fields with `.get()` defaults.
- **Tests hit the real API**: `test_client.py` are integration tests using the anonymous token against the live Cookpad API. `test_types.py` are unit tests with mock data.

## Requirements

- Python >= 3.10 (uses match statements, modern type unions)
- Single runtime dependency: `httpx>=0.27`
- pytest asyncio_mode is set to `"strict"` in pyproject.toml — async test functions must be explicitly marked with `@pytest.mark.asyncio`
