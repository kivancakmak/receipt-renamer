"""Rule-based field extraction from OCR text lines (English + Chinese)."""
import re
from dataclasses import dataclass, field
from datetime import date

TOTAL_KW = re.compile(
    r"(grand\s*total|total\s*due|amount\s*due|total|amount|balance|"
    r"合计|总计|總計|应付|應付|实收|實收|实付|金额|金額|总额|合計)", re.I)
SKIP_KW = re.compile(r"(sub\s*total|subtotal|tax|vat|change|cash|tip|找零|税|稅|小计)", re.I)
NUM = re.compile(r"(?<![\d.,])(\d{1,3}(?:[,，]\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)(?![\d])")

CURRENCY_MAP = [
    (re.compile(r"\bHK\$|\bHKD\b|港币|港幣"), "HKD"),
    (re.compile(r"\bUSD\b|US\$"), "USD"),
    (re.compile(r"\bCNY\b|\bRMB\b|人民币|人民幣|[¥￥]|元"), "CNY"),
    (re.compile(r"\bEUR\b|€"), "EUR"),
    (re.compile(r"\bGBP\b|£"), "GBP"),
    (re.compile(r"\bJPY\b"), "JPY"),
    (re.compile(r"\bSGD\b|S\$"), "SGD"),
    (re.compile(r"\bCAD\b|C\$"), "CAD"),
    (re.compile(r"\bAUD\b|A\$"), "AUD"),
    (re.compile(r"\$"), "USD"),  # bare $ is ambiguous; flagged below
]


@dataclass
class Parsed:
    date: str | None = None
    merchant: str | None = None
    currency: str | None = None
    total: str | None = None
    issues: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return all([self.date, self.merchant, self.currency, self.total]) and not self.issues


def _valid(y, m, d):
    try:
        dt = date(y, m, d)
    except ValueError:
        return None
    return dt if 2000 <= y <= date.today().year + 1 else None


def parse_date(text: str):
    """Return (iso_date | None, issue | None). Ambiguous dd/mm vs mm/dd -> issue."""
    m = re.search(r"(20\d{2})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})", text)
    if m:
        dt = _valid(int(m[1]), int(m[2]), int(m[3]))
        if dt:
            return dt.isoformat(), None
    m = re.search(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2}|\d{2})\b", text)
    if m:
        a, b, y = int(m[1]), int(m[2]), int(m[3])
        y += 2000 if y < 100 else 0
        if a > 12 and b <= 12:
            dt = _valid(y, b, a)
        elif b > 12 and a <= 12:
            dt = _valid(y, a, b)
        elif a == b:
            dt = _valid(y, a, b)
        else:
            return None, "ambiguous date (dd/mm vs mm/dd)"
        if dt:
            return dt.isoformat(), None
    m = re.search(r"\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?,?\s+(20\d{2})", text, re.I)
    if m:
        mon = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"].index(m[2].lower()[:3]) + 1
        dt = _valid(int(m[3]), mon, int(m[1]))
        if dt:
            return dt.isoformat(), None
    m = re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(20\d{2})", text, re.I)
    if m:
        mon = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"].index(m[1].lower()[:3]) + 1
        dt = _valid(int(m[3]), mon, int(m[2]))
        if dt:
            return dt.isoformat(), None
    return None, None


def _to_float(s: str):
    """'1.234,56' / '1,234.56' / '112,99' / '35' -> float; None if not a clean amount."""
    s = s.replace("，", ",")
    m = re.fullmatch(r"(\d{1,3}(?:[.,]\d{3})*|\d+)(?:[.,](\d{2}))?", s)
    if not m:
        return None
    whole = re.sub(r"[.,]", "", m[1])
    return float(f"{whole}.{m[2] or '00'}"), m[2] is not None


def parse_total(lines: list[str]) -> str | None:
    dec, ints = [], []
    for i, ln in enumerate(lines):
        if TOTAL_KW.search(ln) and not SKIP_KW.search(ln):
            for w in [ln] + lines[i + 1:i + 3]:
                if SKIP_KW.search(w):
                    continue
                for tok in re.findall(r"\d[\d.,，]*\d|\d", w):
                    r = _to_float(tok)
                    if r and r[0] > 0:
                        (dec if r[1] else ints).append(r[0])
    cands = dec or ints
    return f"{max(cands):.2f}" if cands else None


def parse_currency(text: str):
    for rx, code in CURRENCY_MAP:
        if rx.search(text):
            if rx.pattern == r"\$":
                return code, "bare $ currency ambiguous"
            return code, None
    return None, None


def parse_merchant(lines: list[str]) -> str | None:
    for ln in lines[:8]:
        s = ln.strip()
        letters = re.findall(r"[A-Za-z一-鿿]", s)
        if len(letters) < 3 or len(s) > 32 or s.count(' ') > 4 or s.endswith(('.', ',', ':')):
            continue
        if re.search(r"receipt|invoice|tel|phone|发票|發票|小票|电话|www\.|http", s, re.I):
            continue
        return s
    return None


def parse_receipt(lines: list[str]) -> Parsed:
    text = "\n".join(lines)
    p = Parsed()
    p.date, di = parse_date(text)
    p.merchant = parse_merchant(lines)
    p.total = parse_total(lines)
    p.currency, ci = parse_currency(text)
    for iss, val in ((di, p.date), (ci, p.currency)):
        if iss:
            p.issues.append(iss)
    for name in ("date", "merchant", "currency", "total"):
        if not getattr(p, name):
            p.issues.append(f"missing {name}")
    return p
