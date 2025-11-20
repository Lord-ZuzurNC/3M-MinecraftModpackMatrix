# Agent Guidelines for 3M-MinecraftModpackMatrix

## Commands
- **Run web app**: `python web.py` (serves on http://localhost:5000)
- **Run CLI**: `python main.py` (interactive URL input)
- **Lint**: `flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics`
- **Test**: `pytest -v --maxfail=3 --disable-warnings`
- **Install deps**: `pip install -r requirements.txt`

## Code Style
- **Python**: 3.10-3.12 compatible
- **Imports**: Group stdlib, third-party, local imports. Use `from x import y` for clarity
- **Type hints**: Use `str | None` syntax (Python 3.10+), Optional for older compatibility
- **Error handling**: Use try/except with specific exceptions, return error dicts for API responses
- **Naming**: snake_case for variables/functions, PascalCase for classes
- **API requests**: Use `safe_request()` wrapper with retries and timeout
- **Caching**: Use `cache_path()` and `is_cache_expired()` helpers, 24h TTL
- **Constants**: UPPER_CASE for configuration values
- **Functions**: Keep functions focused, add docstrings for complex logic
- **Flask routes**: Return JSON responses, handle errors with appropriate status codes