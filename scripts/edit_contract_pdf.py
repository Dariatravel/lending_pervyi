from pathlib import Path

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ROOT = Path("/Users/darya_botova/Documents/New project")
SOURCE_PDF = Path("/Users/darya_botova/Downloads/Договор_Радонежского_Борисов_Даниил.pdf")
OUTPUT_PDF = ROOT / "output" / "contracts" / "Договор_Радонежского_Петрова_Алиса_2026.pdf"

TIMES_REGULAR = "/System/Library/Fonts/Supplemental/Times New Roman.ttf"
TIMES_BOLD = "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf"


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont("ContractTimes", TIMES_REGULAR))
    pdfmetrics.registerFont(TTFont("ContractTimes-Bold", TIMES_BOLD))


def collect_fragments(page):
    fragments = []

    def visitor(text, cm, tm, font_dict, font_size):
        clean = text.replace("\n", "")
        if not clean.strip():
            return
        base_font = ""
        if font_dict:
            base_font = str(font_dict.get("/BaseFont", ""))
        fragments.append(
            {
                "x": float(tm[4]),
                "y": float(tm[5]),
                "size": float(font_size),
                "text": clean,
                "base_font": base_font,
            }
        )

    page.extract_text(visitor_text=visitor)
    return fragments


def should_skip(page_index: int, fragment: dict) -> bool:
    x = fragment["x"]
    y = fragment["y"]

    if page_index == 0:
        if 380 <= x <= 520 and 700 <= y <= 710:
            return True
        if 50 <= x <= 560 and 651 <= y <= 659:
            return True
        if 50 <= x <= 340 and 524 <= y <= 532:
            return True
        if 88 <= x <= 440 and 449 <= y <= 455:
            return True

    if page_index == 1:
        if 50 <= x <= 560 and 690 <= y <= 696:
            return True
        if 50 <= x <= 120 and 677 <= y <= 683:
            return True

    if page_index == 2:
        if 54 <= x <= 320 and 225 <= y <= 395:
            return True

    return False


def font_name(base_font: str) -> str:
    if "Bold" in base_font:
        return "ContractTimes-Bold"
    return "ContractTimes"


def draw_replacements(c: canvas.Canvas, page_index: int) -> None:
    c.setFillColorRGB(0, 0, 0)

    if page_index == 0:
        c.setFont("ContractTimes", 11)
        c.drawString(385.7, 705.5, "“_1_” мая__ 2026_ г.")
        c.drawString(
            54.0,
            655.0,
            "и Г-жа Петрова Алиса Романовна, далее именуемая “Наниматель”, с другой стороны,  заключили",
        )
        c.drawString(54.0, 528.4, "с _1_ мая___2026 г.   по _1_ ___октября___2026 г.")
        c.drawString(90.0, 452.1, "Предоставить указанное помещение Нанимателю с _1 _мая _2026 года.")

    if page_index == 2:
        c.setFont("ContractTimes", 11)
        c.drawString(59.8, 391.6, "ФИО:__Петрова Алиса Романовна _______")
        c.drawString(59.8, 378.9, "________________________________________")
        c.drawString(59.8, 366.4, "Дата рождения: _26.10.2005 г._____________")
        c.drawString(59.8, 353.6, "Место рождения: г. Архангельск")
        c.drawString(59.8, 340.9, "________________________________________")
        c.drawString(59.8, 328.4, "Паспорт: серия 46 25 № 309998")
        c.drawString(59.8, 315.6, "Выдан:_05.02.2026 ГУ МВД России")
        c.drawString(59.8, 303.1, "по Московской области 500-046")
        c.drawString(59.8, 290.4, "________________________________________")
        c.drawString(59.8, 277.6, "________________________________________")
        c.drawString(59.8, 265.1, "Зарегистрирован по адресу: Московская обл.,")
        c.drawString(59.8, 252.3, "г. Коломна, ул. Девичье Поле, д. 12 к. 1, кв. 16")
        c.drawString(59.8, 239.8, "________________________________________")
        c.drawString(59.8, 227.1, "Телефон: ________________________________")

    if page_index == 1:
        c.setFont("ContractTimes", 11)
        c.drawString(
            73.3,
            693.0,
            "В дальнейшем оплата будет производиться ежемесячно, далее не позднее_1_ числа каждого текущего",
        )
        c.drawString(54.0, 680.2, "месяца.")


def rebuild_pdf() -> None:
    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    register_fonts()

    reader = PdfReader(str(SOURCE_PDF))
    c = canvas.Canvas(str(OUTPUT_PDF), pagesize=A4)

    for page_index, page in enumerate(reader.pages):
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        c.setPageSize((width, height))

        for fragment in collect_fragments(page):
            if should_skip(page_index, fragment):
                continue
            c.setFont(font_name(fragment["base_font"]), fragment["size"])
            c.drawString(fragment["x"], fragment["y"], fragment["text"])

        draw_replacements(c, page_index)
        c.showPage()

    c.save()


if __name__ == "__main__":
    rebuild_pdf()
