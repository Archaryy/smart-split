"""Parser tests.

Run from the backend folder:
    .venv\\Scripts\\python.exe -m unittest discover -s tests -v

`fixtures/*.json` are real PaddleOCR outputs from receipt photos.  The other
cases build synthetic OCR output (with bounding boxes) for layouts commonly
seen on bills.
"""

import json
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.receipt_parser import parse_amount, parse_receipt_text  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
LEFT, RIGHT, ROW_H = 60, 600, 34


def load(name):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def box_line(text, x1, x2, y, conf=0.97, tilt=0.0):
    """One OCR fragment. `tilt` rotates the whole page by that many degrees."""
    top, bottom = y, y + 24
    pts = [(x1, top), (x2, top), (x2, bottom), (x1, bottom)]
    if tilt:
        a = math.radians(tilt)
        pts = [(x * math.cos(a) - y_ * math.sin(a), x * math.sin(a) + y_ * math.cos(a)) for x, y_ in pts]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return {
        "text": text,
        "confidence": conf,
        "box": [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))],
        "poly": [[round(x, 1), round(y_, 1)] for x, y_ in pts],
    }


def receipt(rows, tilt=0.0):
    """rows: list of (left_text, right_text) or a plain string (centred line)."""
    lines = []
    for index, row in enumerate(rows):
        y = 100 + index * ROW_H
        if isinstance(row, str):
            lines.append(box_line(row, 180, 480, y, tilt=tilt))
            continue
        left, right = row
        if left:
            lines.append(box_line(left, LEFT, LEFT + 9 * len(left), y, tilt=tilt))
        if right:
            lines.append(box_line(right, RIGHT - 11 * len(right), RIGHT, y, tilt=tilt))
    return {"lines": lines}


class RealReceipts(unittest.TestCase):
    def test_numbered_two_line_items(self):
        r = parse_receipt_text(load("shop_credit"))
        self.assertEqual(r["merchant_name"], "u Shop")
        self.assertEqual(r["transaction_date"], "2023-08-02")
        self.assertEqual([i["name"] for i in r["items"]],
                         ["Indomie Goreng", "Fruit Tea Apple", "Belfood Sosis Bakar"])
        self.assertEqual(r["items"][0]["quantity"], 12)          # 1 lusin
        self.assertEqual(r["items"][0]["total_price"], 36000)
        self.assertEqual(r["items"][1]["unit"], "500 ml")
        self.assertEqual(r["items"][2]["total_price"], 27000)
        self.assertEqual((r["subtotal"], r["total"]), (70000, 70000))
        self.assertEqual(r["reconciliation"]["status"], "ok")

    def test_alfamart_tax_is_included_not_added(self):
        r = parse_receipt_text(load("alfamart"))
        self.assertEqual(r["merchant_name"], "ALFAMART CILANDAK KKO 5")
        self.assertEqual(r["transaction_date"], "2022-03-18")
        self.assertEqual(len(r["items"]), 1)
        self.assertEqual(r["items"][0]["name"], "SUNLG MINT 755")
        self.assertEqual(r["items"][0]["total_price"], 25200)
        self.assertEqual(r["tax"], 2291)
        self.assertTrue(r["tax_included"])
        self.assertEqual(r["total"], 25200)                      # not 27,491
        self.assertEqual(r["reconciliation"]["status"], "ok")


class NoisyRealReceipt(unittest.TestCase):
    """Real OCR output from a degraded photo: columns fused ("125,20025,200"), typos."""

    def test_fused_columns_and_ocr_typos(self):
        r = parse_receipt_text(load("alfamart_noisy"))
        self.assertEqual(len(r["items"]), 1)
        self.assertEqual(r["items"][0]["name"], "SUNLG MINT 755")
        self.assertEqual(r["items"][0]["quantity"], 1)
        self.assertEqual(r["items"][0]["total_price"], 25200)
        self.assertEqual(r["tax"], 2291)
        self.assertEqual(r["total"], 25200)


class LegacyBoxlessInput(unittest.TestCase):
    """OCR lines without boxes still parse (sequential fallback)."""

    def test_sample(self):
        texts = [
            "u Shop", "Jl. Dr. Ir. H. Soekarno No.19,Me", "2023-08-02",
            "1. Indomie Goreng", "1 lusin x 36,000", "Rp 36.000",
            "2. Fruit Tea Apple", "1 500 ml × 7,000", "Rp 7.000",
            "3. Belfood Sosis Bakar", "1 × 27,000", "Rp 27.000",
            "Total QTY:14", "Sub Total", "Rp 70.000", "Total", "Rp 70.000",
            "Tipe: kredit", "Sisa limit: Rp 10.000",
            "History Pembayaran Utang:", "02/08/2023 Cash", "Rp 60.000",
        ]
        r = parse_receipt_text({"lines": [{"text": t, "confidence": 0.95} for t in texts]})
        self.assertEqual(len(r["items"]), 3)
        self.assertEqual(r["items"][0]["quantity"], 12)
        self.assertEqual(r["items"][0]["total_price"], 36000)
        self.assertEqual(r["items"][1]["unit"], "500 ml")
        self.assertEqual(r["items"][2]["total_price"], 27000)
        self.assertEqual((r["subtotal"], r["total"]), (70000, 70000))


class Layouts(unittest.TestCase):
    def test_restaurant_one_line_items_with_added_tax(self):
        r = parse_receipt_text(receipt([
            "WARUNG MAKAN SEDERHANA", "Jl. Merdeka No. 12", "Meja 5",
            ("Nasi Goreng Spesial", "35.000"),
            ("2 Es Teh Manis", "16.000"),
            ("Sate Ayam x3", "45.000"),
            ("Subtotal", "96.000"),
            ("Service 5%", "4.800"),
            ("PB1 10%", "9.600"),
            ("Total", "110.400"),
        ]))
        self.assertEqual([i["name"] for i in r["items"]],
                         ["Nasi Goreng Spesial", "Es Teh Manis", "Sate Ayam"])
        self.assertEqual([i["quantity"] for i in r["items"]], [1, 2, 3])
        self.assertEqual([i["total_price"] for i in r["items"]], [35000, 16000, 45000])
        self.assertEqual(r["service_charge"], 4800)
        self.assertEqual(r["tax"], 9600)
        self.assertFalse(r["tax_included"])
        self.assertEqual(r["total"], 110400)
        self.assertEqual(r["reconciliation"]["status"], "ok")

    def test_usd_receipt_with_decimals(self):
        r = parse_receipt_text(receipt([
            "Joe's Diner", "123 Main Street", "03/14/2024",
            ("Cheeseburger", "$12.50"),
            ("Fries", "$4.00"),
            ("Iced Tea", "$3.25"),
            ("Subtotal", "$19.75"),
            ("Tax", "$1.58"),
            ("Total", "$21.33"),
        ]))
        self.assertEqual(r["currency"], "USD")
        self.assertEqual(r["transaction_date"], "2024-03-14")
        self.assertEqual([i["total_price"] for i in r["items"]], [12.5, 4, 3.25])
        self.assertEqual(r["subtotal"], 19.75)
        self.assertEqual(r["tax"], 1.58)
        self.assertEqual(r["total"], 21.33)
        self.assertEqual(r["reconciliation"]["status"], "ok")

    def test_column_layout(self):
        r = parse_receipt_text(receipt([
            "TOKO MAJU JAYA",
            ("Aqua 600ml 2 4.000", "8.000"),
            ("Roti Tawar 1 15.500", "15.500"),
            ("Total", "23.500"),
            ("Tunai", "50.000"),
            ("Kembali", "26.500"),
        ]))
        self.assertEqual(len(r["items"]), 2)
        self.assertEqual(r["items"][0]["name"], "Aqua 600ml")
        self.assertEqual(r["items"][0]["quantity"], 2)
        self.assertEqual(r["items"][0]["unit_price"], 4000)
        self.assertEqual(r["total"], 23500)

    def test_name_line_then_detail_line_with_item_discount(self):
        r = parse_receipt_text(receipt([
            "INDOMARET", "Jl. Sudirman 5",
            ("KOPI SUSU BOTOL", ""),
            ("2 x 18.000", "36.000"),
            ("ROTI COKLAT", ""),
            ("1 x 9.500", "9.500"),
            ("Diskon", "-5.000"),
            ("Total Belanja", "40.500"),
            ("Tunai", "50.000"),
            ("Kembali", "9.500"),
        ]))
        self.assertEqual([i["name"] for i in r["items"]], ["KOPI SUSU BOTOL", "ROTI COKLAT"])
        self.assertEqual(r["items"][0]["quantity"], 2)
        self.assertEqual(r["items"][0]["total_price"], 36000)
        self.assertEqual(r["discount"], 5000)
        self.assertEqual(r["total"], 40500)
        self.assertEqual(r["reconciliation"]["status"], "ok")

    def test_item_whose_name_starts_with_a_number_keeps_its_name(self):
        r = parse_receipt_text(receipt([
            "KANTIN", ("7 Up", "8.000"), ("Total", "8.000"),
        ]))
        self.assertEqual(r["items"][0]["name"], "7 Up")
        self.assertEqual(r["items"][0]["quantity"], 1)

    def test_weighted_item(self):
        r = parse_receipt_text(receipt([
            "PASAR SWALAYAN", ("Apel Fuji 0.35 kg x 40.000", "14.000"), ("Total", "14.000"),
        ]))
        item = r["items"][0]
        self.assertEqual(item["name"], "Apel Fuji")
        self.assertEqual(item["quantity"], 0.35)
        self.assertEqual(item["unit"], "kg")
        self.assertEqual(item["total_price"], 14000)

    def test_european_number_format(self):
        self.assertEqual(float(parse_amount("1.234,50")), 1234.5)
        self.assertEqual(float(parse_amount("1,234.50")), 1234.5)
        self.assertEqual(int(parse_amount("1.234.567")), 1234567)
        self.assertEqual(int(parse_amount("Rp 25.200")), 25200)
        self.assertEqual(int(parse_amount("35000")), 35000)

    def test_plain_numbers_without_separators(self):
        r = parse_receipt_text(receipt([
            "KEDAI KOPI", ("Americano", "28000"), ("Croissant", "22000"), ("Total", "50000"),
        ]))
        self.assertEqual([i["total_price"] for i in r["items"]], [28000, 22000])
        self.assertEqual(r["total"], 50000)

    def test_ocr_garbled_labels(self):
        r = parse_receipt_text(receipt([
            "CAFE LUNA", ("Latte", "30.000"), ("Brownie", "25.000"),
            ("Sub Tota1", "55.000"), ("PPN 11%", "6.050"), ("Tota1", "61.050"),
        ]))
        self.assertEqual(len(r["items"]), 2)
        self.assertEqual(r["tax"], 6050)
        self.assertEqual(r["total"], 61050)
        self.assertEqual(r["reconciliation"]["status"], "ok")

    def test_quantity_glued_to_price_by_ocr(self):
        # OCR read "1   25,200" as "125,200"
        r = parse_receipt_text(receipt([
            "ALFAMART", ("SUNLG MINT 755 125,200", "25,200"), ("Total Item 1", "25,200"),
        ]))
        self.assertEqual(r["items"][0]["name"], "SUNLG MINT 755")
        self.assertEqual(r["items"][0]["quantity"], 1)
        self.assertEqual(r["items"][0]["unit_price"], 25200)

    def test_glued_digits_that_do_not_add_up_stay_in_the_name(self):
        r = parse_receipt_text(receipt([
            "TOKO", ("Kabel Data 125,200", "40,000"), ("Total", "40,000"),
        ]))
        self.assertEqual(r["items"][0]["total_price"], 40000)
        self.assertEqual(r["items"][0]["quantity"], 1)

    def test_trailing_tax_flag_letters_are_ignored(self):
        r = parse_receipt_text(receipt([
            "SUPERMARKET", ("MILK 1L", "18.900 T"), ("EGGS 10", "27.500 T"), ("Total", "46.400"),
        ]))
        self.assertEqual([i["total_price"] for i in r["items"]], [18900, 27500])


class Robustness(unittest.TestCase):
    def test_tilted_photo(self):
        rows = [
            "WARUNG BU TINI", "Jl. Melati 3",
            ("Nasi Ayam Bakar", "28.000"), ("Es Jeruk", "8.000"), ("Tahu Goreng", "6.000"),
            ("Subtotal", "42.000"), ("Total", "42.000"),
        ]
        for tilt in (-6, -3, 3, 6):
            with self.subTest(tilt=tilt):
                r = parse_receipt_text(receipt(rows, tilt=tilt))
                self.assertEqual([i["total_price"] for i in r["items"]], [28000, 8000, 6000])
                self.assertEqual(r["total"], 42000)

    def test_mismatch_is_reported(self):
        r = parse_receipt_text(receipt([
            "TOKO A", ("Barang 1", "10.000"), ("Barang 2", "20.000"),
            ("Subtotal", "45.000"), ("Total", "45.000"),
        ]))
        self.assertEqual(r["reconciliation"]["status"], "mismatch")
        self.assertTrue(r["warnings"])

    def test_header_lines_are_not_items(self):
        r = parse_receipt_text(receipt([
            "TOKO SERBA ADA", "Jl. Raya Bogor No. 45", "Telp: 021 8765 4321",
            "Kasir: Rina 01", "Order #1042",
            ("Teh Botol", "5.000"), ("Total", "5.000"),
        ]))
        self.assertEqual([i["name"] for i in r["items"]], ["Teh Botol"])

    def test_junk_and_empty_input_do_not_crash(self):
        for payload in ({}, {"lines": []}, {"lines": [{"text": "###", "confidence": 0.2}]}):
            r = parse_receipt_text(payload)
            self.assertEqual(r["items"], [])
            self.assertTrue(r["warnings"])

    def test_no_printed_total_uses_cash_minus_change(self):
        r = parse_receipt_text(receipt([
            "MINIMART", ("Snack", "12.000"), ("Minuman", "8.000"),
            ("Tunai", "50.000"), ("Kembalian", "30.000"),
        ]))
        self.assertEqual(r["total"], 20000)


if __name__ == "__main__":
    unittest.main()
