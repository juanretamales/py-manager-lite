import unittest
from app.services.currency_service import CurrencyService, format_currency, CURRENCY_PRESETS


class TestCurrencyService(unittest.TestCase):
    def setUp(self):
        self.svc = CurrencyService()

    def test_default_clp_formatting(self):
        """Valida que el formato estándar chileno use punto para miles y sin decimales."""
        cfg = {
            "preset": "CLP",
            "code": "CLP",
            "symbol": "$",
            "symbol_position": "prefix",
            "thousand_separator": ".",
            "decimal_separator": ",",
            "decimals": 0,
            "show_code": False,
        }
        self.assertEqual(self.svc.format_amount(1500000, cfg), "$ 1.500.000")
        self.assertEqual(self.svc.format_amount(0, cfg), "$ 0")
        self.assertEqual(self.svc.format_amount(-45000, cfg), "-$ 45.000")
        self.assertEqual(self.svc.format_amount(1250.7, cfg), "$ 1.251")

    def test_clp_with_code_suffix(self):
        """Valida que al activar show_code se añada CLP al final."""
        cfg = {
            "preset": "CLP",
            "code": "CLP",
            "symbol": "$",
            "symbol_position": "prefix",
            "thousand_separator": ".",
            "decimal_separator": ",",
            "decimals": 0,
            "show_code": True,
        }
        self.assertEqual(self.svc.format_amount(2500000, cfg), "$ 2.500.000 CLP")
        self.assertEqual(self.svc.format_amount(-1000, cfg), "-$ 1.000 CLP")

    def test_uf_formatting(self):
        """Valida que para UF se use coma decimal y el sufijo UF."""
        cfg = {
            "preset": "UF",
            "code": "UF",
            "symbol": "UF",
            "symbol_position": "suffix",
            "thousand_separator": ".",
            "decimal_separator": ",",
            "decimals": 2,
            "show_code": False,
        }
        self.assertEqual(self.svc.format_amount(35.5, cfg), "35,50 UF")
        self.assertEqual(self.svc.format_amount(1250.75, cfg), "1.250,75 UF")
        self.assertEqual(self.svc.format_amount(-12.4, cfg), "-12,40 UF")

    def test_usd_formatting(self):
        """Valida que para USD se use coma de miles y punto decimal."""
        cfg = {
            "preset": "USD",
            "code": "USD",
            "symbol": "$",
            "symbol_position": "prefix",
            "thousand_separator": ",",
            "decimal_separator": ".",
            "decimals": 2,
            "show_code": False,
        }
        self.assertEqual(self.svc.format_amount(1250.5, cfg), "$ 1,250.50")
        self.assertEqual(self.svc.format_amount(1000000, cfg), "$ 1,000,000.00")

    def test_convenience_format_currency(self):
        """Valida la función global format_currency."""
        res = format_currency(1000)
        self.assertIsInstance(res, str)
        self.assertTrue(len(res) > 0)

    def test_presets_exist(self):
        """Valida que existan los presets solicitados."""
        self.assertIn("CLP", CURRENCY_PRESETS)
        self.assertIn("UF", CURRENCY_PRESETS)
        self.assertIn("USD", CURRENCY_PRESETS)
        self.assertIn("EUR", CURRENCY_PRESETS)


if __name__ == "__main__":
    unittest.main()
