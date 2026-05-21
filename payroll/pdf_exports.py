from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


def money(value):
    return f"Rs. {value:,.2f}"


def clean_text(value):
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("\r", " ").strip()


def fit_text(text, max_width, font_name="Helvetica", font_size=7):
    """
    Shortens text so it never crosses the available width.
    """
    text = clean_text(text)

    if stringWidth(text, font_name, font_size) <= max_width:
        return text

    ellipsis = "..."
    while text and stringWidth(text + ellipsis, font_name, font_size) > max_width:
        text = text[:-1]

    return text + ellipsis if text else ""


def draw_fit_string(c, x, y, text, max_width, font_name="Helvetica", font_size=7):
    fitted = fit_text(text, max_width, font_name, font_size)
    c.setFont(font_name, font_size)
    c.drawString(x, y, fitted)


def draw_label_value(c, label_x, value_x, y, label, value, value_max_width):
    c.setFont("Helvetica-Bold", 7)
    c.drawString(label_x, y, label)

    draw_fit_string(
        c=c,
        x=value_x,
        y=y,
        text=value,
        max_width=value_max_width,
        font_name="Helvetica",
        font_size=7,
    )


def draw_form_xix_slip(c, payroll_run, payroll_line, x, y, width, height):
    """
    Draws one Form XIX payslip inside a fixed rectangle.
    All long text is truncated so it stays inside the payslip border.
    """

    padding = 5 * mm
    left = x + padding
    right = x + width - padding
    top = y + height - padding
    usable_width = width - (2 * padding)

    c.setStrokeColor(colors.black)
    c.setLineWidth(1)
    c.rect(x, y, width, height)

    # Header
    company_area_width = usable_width * 0.62
    title_area_x = left + company_area_width + 2 * mm

    c.setFont("Helvetica-Bold", 10)
    draw_fit_string(
        c,
        left,
        top,
        payroll_run.company.name.upper(),
        company_area_width,
        "Helvetica-Bold",
        10,
    )

    address = payroll_run.company.address or ""
    draw_fit_string(
        c,
        left,
        top - 4 * mm,
        address,
        company_area_width,
        "Helvetica",
        7,
    )

    if payroll_run.company.gst_number:
        draw_fit_string(
            c,
            left,
            top - 8 * mm,
            f"GST: {payroll_run.company.gst_number}",
            company_area_width,
            "Helvetica",
            7,
        )

    c.setFont("Helvetica-Bold", 13)
    c.drawRightString(right, top, "FORM XIX")

    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(right, top - 5 * mm, "Pay Slip")

    c.line(left, top - 11 * mm, right, top - 11 * mm)

    current_y = top - 16 * mm

    # Two-column metadata layout
    label1_x = left
    value1_x = left + 18 * mm
    label2_x = left + usable_width * 0.55
    value2_x = label2_x + 15 * mm

    value1_width = label2_x - value1_x - 4 * mm
    value2_width = right - value2_x

    draw_label_value(
        c,
        label1_x,
        value1_x,
        current_y,
        "Month:",
        payroll_run.payroll_cycle.name,
        value1_width,
    )

    draw_label_value(
        c,
        label2_x,
        value2_x,
        current_y,
        "PO:",
        payroll_run.po.po_number,
        value2_width,
    )

    current_y -= 5 * mm

    draw_label_value(
        c,
        label1_x,
        value1_x,
        current_y,
        "Period:",
        f"{payroll_run.payroll_cycle.period_start} to {payroll_run.payroll_cycle.period_end}",
        usable_width - 18 * mm,
    )

    current_y -= 5 * mm

    draw_label_value(
        c,
        label1_x,
        value1_x,
        current_y,
        "Employee:",
        payroll_line.labourer_name,
        value1_width,
    )

    draw_label_value(
        c,
        label2_x,
        value2_x,
        current_y,
        "Code:",
        payroll_line.labour_code,
        value2_width,
    )

    current_y -= 5 * mm

    draw_label_value(
        c,
        label1_x,
        value1_x,
        current_y,
        "Designation:",
        payroll_line.skill_group_name,
        value1_width,
    )

    draw_label_value(
        c,
        label2_x,
        value2_x,
        current_y,
        "Days:",
        payroll_line.working_days,
        value2_width,
    )

    current_y -= 5 * mm

    draw_label_value(
        c,
        label1_x,
        value1_x,
        current_y,
        "Basic Hrs:",
        payroll_line.basic_hours,
        value1_width,
    )

    draw_label_value(
        c,
        label2_x,
        value2_x,
        current_y,
        "OT Hrs:",
        payroll_line.overtime_hours,
        value2_width,
    )

    current_y -= 7 * mm

    # Tables
    table_top = current_y
    table_height = 52 * mm
    col_gap = 4 * mm
    table_width = (usable_width - col_gap) / 2

    earnings_x = left
    deductions_x = left + table_width + col_gap

    earnings = [
        ("Basic Wage", payroll_line.basic_wage),
        ("JAC Allowance", payroll_line.jac_allowance),
        ("Other Cash", payroll_line.other_cash),
        ("Overtime", payroll_line.overtime_amount),
        ("Additional Allow.", payroll_line.additional_allowance),
        ("Gross Wage", payroll_line.gross_wage),
    ]

    deductions = [
        ("PF Deduction", payroll_line.pf_deduction),
        ("ESI Deduction", payroll_line.esi_deduction),
        ("Other Advance", payroll_line.other_advance),
        ("Festival Advance", payroll_line.festival_advance),
        ("Total Deduction", payroll_line.total_deductions),
        ("Net Salary", payroll_line.net_pay),
    ]

    draw_table(c, earnings_x, table_top, table_width, table_height, "Earnings", earnings)
    draw_table(c, deductions_x, table_top, table_width, table_height, "Deductions", deductions)

    # Footer
    footer_y = y + 10 * mm

    c.setFont("Helvetica", 7)
    draw_fit_string(
        c,
        left,
        footer_y,
        "Prepared By: __________________",
        usable_width / 2 - 2 * mm,
        "Helvetica",
        7,
    )

    c.drawRightString(
        right,
        footer_y,
        "Employee Signature: __________________",
    )


def draw_table(c, x, top_y, width, height, title, rows):
    row_height = height / (len(rows) + 1)

    c.setFillColor(colors.HexColor("#111827"))
    c.rect(x, top_y - row_height, width, row_height, fill=True, stroke=True)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawCentredString(x + width / 2, top_y - row_height + 3.2 * mm, title)

    c.setFillColor(colors.black)

    y = top_y - row_height

    label_width = width * 0.52
    amount_width = width * 0.42

    for index, (label, amount) in enumerate(rows, start=1):
        y -= row_height

        if index == len(rows):
            c.setFillColor(colors.HexColor("#E5E7EB"))
            c.rect(x, y, width, row_height, fill=True, stroke=True)
            c.setFillColor(colors.black)
            font_name = "Helvetica-Bold"
        else:
            c.rect(x, y, width, row_height, fill=False, stroke=True)
            font_name = "Helvetica"

        draw_fit_string(
            c,
            x + 2 * mm,
            y + 3 * mm,
            label,
            label_width,
            font_name,
            7,
        )

        amount_text = money(amount)
        fitted_amount = fit_text(amount_text, amount_width, font_name, 7)

        c.setFont(font_name, 7)
        c.drawRightString(x + width - 2 * mm, y + 3 * mm, fitted_amount)


def build_single_form_xix_pdf(payroll_line):
    buffer = BytesIO()

    c = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

    payroll_run = payroll_line.payroll_run

    slip_x = 15 * mm
    slip_y = page_height - 150 * mm
    slip_width = page_width - 30 * mm
    slip_height = 130 * mm

    draw_form_xix_slip(
        c=c,
        payroll_run=payroll_run,
        payroll_line=payroll_line,
        x=slip_x,
        y=slip_y,
        width=slip_width,
        height=slip_height,
    )

    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer


def build_bulk_form_xix_pdf(payroll_run):
    buffer = BytesIO()

    c = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

    margin = 8 * mm
    gap = 5 * mm

    slip_width = (page_width - 2 * margin - gap) / 2
    slip_height = (page_height - 2 * margin - gap) / 2

    positions = [
        (margin, page_height - margin - slip_height),
        (margin + slip_width + gap, page_height - margin - slip_height),
        (margin, margin),
        (margin + slip_width + gap, margin),
    ]

    lines = payroll_run.lines.all().order_by("labourer_name")

    for index, line in enumerate(lines):
        if index > 0 and index % 4 == 0:
            c.showPage()

        x_pos, y_pos = positions[index % 4]

        draw_form_xix_slip(
            c=c,
            payroll_run=payroll_run,
            payroll_line=line,
            x=x_pos,
            y=y_pos,
            width=slip_width,
            height=slip_height,
        )

    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer