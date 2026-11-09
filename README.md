# Receipt Renamer

Renames scanned receipts (PDF/JPG/PNG, English/Chinese) to `YYYY-MM-DD_Merchant_CurrencyAmount.ext`.
Originals are never modified: files are **copied** to `output/renamed/`; unclear ones go to `output/review/` untouched. `output/log.csv` maps original -> new name with the reason for any review flag.

## Setup
```
pip install -r requirements.txt
set GEMINI_API_KEY=...         # free key from aistudio.google.com (fallback LLM)
set RECEIPT_PROVIDER=ollama    # or: local Ollama (ollama pull qwen2.5vl), fully offline
# or ANTHROPIC_API_KEY for Claude
```

## Usage
```
python rename_receipts.py samples --dry-run      # preview, writes only log.csv
python rename_receipts.py samples                # do it
python rename_receipts.py samples --no-llm       # fully offline (confidential mode)
python rename_receipts.py samples --llm-only     # skip local OCR
```

Pipeline: LLM vision first (Gemini/Ollama/Claude); if unavailable or it fails, RapidOCR + rules. Anything incomplete, ambiguous or low-confidence -> `review/`.
Never guessed: ambiguous dd/mm dates, bare `$` currency, missing total/merchant.

Confidentiality: with `--no-llm` nothing leaves the machine. Otherwise only low-confidence receipts are sent to the Anthropic API; get client consent first.

Test data: `git clone https://github.com/JensWalter/my-receipts samples`
Tests: `python -m pytest tests`
