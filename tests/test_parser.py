import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from receipt_pipeline.parser import parse_receipt, parse_date
from receipt_pipeline.namer import build_name, sanitize


def test_english_receipt():
    p = parse_receipt(["Joe's Coffee", "Tel 555", "2024-03-15 10:22", "Subtotal 10.00", "Tax 0.80", "TOTAL €10.80"])
    assert p.complete and p.date == "2024-03-15" and p.total == "10.80" and p.currency == "EUR"


def test_chinese_receipt():
    p = parse_receipt(["星巴克咖啡", "2023年12月5日", "合计 ¥ 1,288.50"])
    assert p.complete and p.date == "2023-12-05" and p.currency == "CNY" and p.total == "1288.50"


def test_ambiguous_date_flagged():
    assert parse_date("03/04/2024") == (None, "ambiguous date (dd/mm vs mm/dd)")
    assert parse_date("25/04/2024")[0] == "2024-04-25"


def test_bare_dollar_flagged():
    p = parse_receipt(["Shop Name Ltd", "2024-01-02", "Total $5.00"])
    assert not p.complete


def test_missing_total_flagged():
    p = parse_receipt(["Shop Name Ltd", "2024-01-02", "Thanks"])
    assert not p.complete


def test_name():
    assert build_name("2024-03-15", 'A/B: "Cafe"', "CNY", "12.50", ".PDF") == "2024-03-15_AB-Cafe_CNY12.50.pdf"
    assert sanitize("星巴克 咖啡") == "星巴克-咖啡"
