#!/usr/bin/env python3
import unittest

from core.raw_trade_import import parse_raw_trades


PLATFORM_SAMPLE = """
/dump Instrument Entry Time (EET) Type Side Amount Entry Price SL Price TP Price Exit Time (EET) Exit Price Fee Swap P&L Net P&L Order ID Position ID
Actions

Currency flag
GBPUSD
Currency flag
2026/03/30 15:40:23 Take profit Sell 1.50 1.32342
1.32339
1.32100 2026/03/30 16:34:36 1.32096 $0.00 $0.00 $369.00 $369.00 7277816997974812928 7277816997857708067

Currency flag
NAS100
2026/03/30 15:15:14 Market Sell 0.02 23,287.50
23,341.12
23,049.81 2026/03/30 15:23:26 23,311.80 $0.00 $0.00 -$48.60 -$48.60 7277816997974810773 7277816997857707210
"""


class RawTradeImportTests(unittest.TestCase):
    def test_platform_export_with_wrapped_lines_is_parsed(self):
        trades = parse_raw_trades(PLATFORM_SAMPLE, tz_offset_hours=2)

        self.assertEqual(len(trades), 2)
        self.assertEqual(trades[0]["symbol"], "GBPUSD")
        self.assertEqual(trades[0]["external_id"], "7277816997974812928")
        self.assertEqual(trades[0]["pnl_usd"], 369.0)
        self.assertEqual(trades[1]["symbol"], "US100")
        self.assertEqual(trades[1]["outcome"], "SL")

    def test_combined_results_are_sorted_latest_first(self):
        trades = parse_raw_trades(PLATFORM_SAMPLE, tz_offset_hours=2)
        self.assertGreater(trades[0]["ts_open"], trades[1]["ts_open"])


if __name__ == "__main__":
    unittest.main()
