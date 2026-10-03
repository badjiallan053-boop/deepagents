import unittest
from datetime import datetime, timezone

from telegram_parser import extract_mints, parse_telegram_message


class TelegramParserTests(unittest.TestCase):
    def test_explicit_ca_is_extracted_once(self):
        mint = "So11111111111111111111111111111111111111112"
        calls = parse_telegram_message(
            channel="@alpha",
            message_id=7,
            published_at=datetime(2026, 10, 3, tzinfo=timezone.utc),
            text=f"BUY NOW CA: {mint} https://pump.fun/coin/{mint}",
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].mint, mint)
        self.assertEqual(calls[0].call_type, "BUY")
        self.assertGreaterEqual(calls[0].parse_confidence, 0.98)

    def test_no_valid_pubkey_no_signal(self):
        calls = parse_telegram_message(
            channel="@noise",
            message_id=1,
            published_at=0,
            text="BUY $DOGE this is just ticker chatter",
        )
        self.assertEqual(calls, [])

    def test_sell_classification(self):
        mint = "So11111111111111111111111111111111111111112"
        calls = parse_telegram_message(
            channel="@alpha",
            message_id=8,
            published_at=0,
            text=f"TAKE PROFIT / SELL {mint}",
        )
        self.assertEqual(calls[0].call_type, "SELL")


if __name__ == "__main__":
    unittest.main()
