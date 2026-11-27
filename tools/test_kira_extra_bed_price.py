import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from kira_public_export import render_prices


class ExtraBedTest(unittest.TestCase):
    def test_extra_has_own_style_in_both_modes_and_keeps_note(self):
        group = dict(title="Номера", note="За троих", mode="rows",
                     rows=[dict(amount="4000", period="июнь", note=""),
                           dict(amount="500", period="четвёртое допместо", note="за ночь", extra=True)],
                     freeText="4000₽ - июнь\n500₽ - четвёртое допместо")
        for mode in ("text", "rows"):
            doc = {"description":"Бронирование 2027","groups":[{**group, "mode":mode}]}
            soup = BeautifulSoup(render_prices(doc), "html.parser")
            self.assertEqual(soup.select_one("li.price-card__extra").text, "500₽ - четвёртое допместо · за ночь")
            self.assertEqual(soup.select_one("li:not(.price-card__extra)").text, "4000₽ - июнь")
