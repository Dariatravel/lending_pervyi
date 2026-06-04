from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


BASE_DIR = Path("/Users/darya_botova/Documents/New project")
OUTPUT_PATH = BASE_DIR / "output" / "pdf" / "zayavlenie_botovoy_o_zaklyuchenii_dogovora_nayma.pdf"
FONT_PATH = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
FONT_BOLD_PATH = Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont("ArialCustom", str(FONT_PATH)))
    pdfmetrics.registerFont(TTFont("ArialCustom-Bold", str(FONT_BOLD_PATH)))


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="BodyRu",
            parent=styles["Normal"],
            fontName="ArialCustom",
            fontSize=12,
            leading=17,
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="RecipientRu",
            parent=styles["Normal"],
            fontName="ArialCustom",
            fontSize=12,
            leading=16,
            alignment=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SubjectRu",
            parent=styles["Normal"],
            fontName="ArialCustom-Bold",
            fontSize=12,
            leading=16,
            alignment=1,
        )
    )
    return styles


def main() -> None:
    register_fonts()
    styles = build_styles()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(OUTPUT_PATH),
        pagesize=A4,
        leftMargin=25 * mm,
        rightMargin=25 * mm,
        topMargin=22 * mm,
        bottomMargin=22 * mm,
    )

    recipient_lines = [
        "Директору Департамента недвижимости",
        "ГлавУпДК при МИД России",
        "К. Н. Гладкову",
        "от Ботовой Дарьи Александровны,",
        "тел. 8 (982) 330-14-00",
    ]

    body_paragraphs = [
        "Уважаемый Константин Николаевич,",
        (
            "Прошу заключить со мной договор найма на квартиру N 432-433 "
            "по адресу: Ленинский проспект, 45."
        ),
        (
            "Обязуюсь выполнять все условия арендного договора. "
            "Своевременную оплату гарантирую. Мне известно фактическое состояние "
            "данного объекта недвижимости, и я не имею претензий к его состоянию."
        ),
        (
            "Прилагаю к письму свои паспортные данные, а также справки о доходах "
            "за 2025-2026 гг."
        ),
        (
            "Также подтверждаю, что на данный момент не являюсь банкротом, "
            "в отношении меня отсутствуют процедуры взыскания задолженностей "
            "и какие-либо ограничения, препятствующие заключению договора найма."
        ),
        "С уважением,",
        "Ботова Дарья Александровна",
        "тел. 8 (982) 330-14-00",
        "e-mail: dartiande@yandex.ru",
    ]

    story = []
    for line in recipient_lines:
        story.append(Paragraph(line, styles["RecipientRu"]))
    story.append(Spacer(1, 14 * mm))
    story.append(Paragraph("Заявление о заключении договора найма", styles["SubjectRu"]))
    story.append(Spacer(1, 10 * mm))

    for index, paragraph in enumerate(body_paragraphs):
        story.append(Paragraph(paragraph, styles["BodyRu"]))
        if index == 0:
            story.append(Spacer(1, 6 * mm))
        elif index < len(body_paragraphs) - 4:
            story.append(Spacer(1, 5 * mm))
        else:
            story.append(Spacer(1, 3.5 * mm))

    doc.build(story)
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
