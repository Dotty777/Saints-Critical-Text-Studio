# Contributing to Saints Critical Text Studio

Contributions from textual critics, philologists, open-source developers, and AI agents are welcome under the [MIT License](LICENSE).

## Development Workflow

1. **Zero-Dependency Baseline**: Keep core modules (`studio/*`, `app.py`, `cli.py`) compatible with standard Python `>= 3.11` stdlib (`tkinter`, `sqlite3`, `difflib`, `xml.etree.ElementTree`, `unicodedata`). Optional accelerators (`pymupdf` for PDF extraction, `google-genai >= 3.2.0` for optional cloud calls) must be imported lazily inside `try/except ImportError` blocks.
2. **Unicode Normalization**: Normalize all ingested Greek, Hebrew, and Latin strings to `NFC` (`unicodedata.normalize("NFC", ...)`), especially for pointed Tiberian Hebrew where combining-class ordering affects string comparison.
3. **Testing**: Add unit tests in `tests/test_studio.py` for every new parser, orthographic rule, or Brain provider, and verify offline execution via:
   ```powershell
   python -m unittest discover -s tests -v
   ```
