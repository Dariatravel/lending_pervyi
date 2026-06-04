from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


BASE_DIR = Path("/Users/darya_botova/Documents/New project")
OUTPUT_PATH = BASE_DIR / "output" / "pdf" / "delovoe_pismo_o_pereoformlenii_dogovora.pdf"
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
        "от Максимова Ильи Игоревича,",
        "тел. 8 (987) 889-70-06",
    ]

    body_paragraphs = [
        "Уважаемый Константин Николаевич,",
        (
            "Обращаюсь к вам с просьбой переоформить на другое ответственное лицо "
            "договор N 25040070 от 04.09.2025 квартиры N 432-433 по адресу: "
            "г. Москва, Ленинский проспект, дом 45."
        ),
        (
            "Такая необходимость возникла в связи с изменением моих жизненных "
            "обстоятельств: в ближайшее время я планирую переезд в другой город, "
            "поэтому заранее и добросовестно уведомляю вас и прошу оформить "
            "фактическое изменение ответственности."
        ),
        (
            "Новый арендатор уже знаком с условиями проживания и готов в полном "
            "объеме принять на себя обязательства по договору. В дальнейшем он "
            "обязуется своевременно вносить все платежи, соблюдать условия аренды, "
            "поддерживать квартиру в надлежащем состоянии, а также внести залоговую "
            "сумму в полном объеме."
        ),
        (
            "Уверен, что переоформление договора на другого арендатора позволит "
            "компании избежать необходимости поиска нового арендатора, проведения "
            "отбора и возможных периодов простоя квартиры."
        ),
        (
            "Новым арендатором будет выступать Ботова Дарья Александровна, "
            "1988 г. р., тел. 8 (982) 330-14-00. О своем намерении она также "
            "известит вас отдельным письмом с указанием паспортных данных, "
            "подтверждением доходов и иными необходимыми сведениями."
        ),
        "С уважением,",
        "Максимов Илья Игоревич",
        "тел. 8 (987) 889-70-06",
    ]

    story = []
    for line in recipient_lines:
        story.append(Paragraph(line, styles["RecipientRu"]))
    story.append(Spacer(1, 14 * mm))
    story.append(Paragraph("Заявление о переоформлении договора", styles["SubjectRu"]))
    story.append(Spacer(1, 10 * mm))

    for index, paragraph in enumerate(body_paragraphs):
        story.append(Paragraph(paragraph, styles["BodyRu"]))
        if index == 0:
            story.append(Spacer(1, 6 * mm))
        elif index < len(body_paragraphs) - 3:
            story.append(Spacer(1, 5 * mm))
        else:
            story.append(Spacer(1, 3.5 * mm))

    doc.build(story)
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
