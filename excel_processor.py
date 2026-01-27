"""Excel processor for Fernwärme billing spreadsheet."""

import calendar
from datetime import date
from pathlib import Path
from openpyxl import load_workbook


def get_quarter_dates(quarter: str) -> dict:
    """
    Calculate all relevant dates for a quarter.

    Args:
        quarter: Quarter string like "2025Q4"

    Returns:
        Dictionary with start_date, end_date, prev_end_date
    """
    year = int(quarter[:4])
    q = int(quarter[-1])

    # Quarter start and end months
    quarter_months = {
        1: (1, 3),  # Jan-Mar
        2: (4, 6),  # Apr-Jun
        3: (7, 9),  # Jul-Sep
        4: (10, 12),  # Oct-Dec
    }

    start_month, end_month = quarter_months[q]

    # Last day of quarter
    last_day = calendar.monthrange(year, end_month)[1]
    end_date = date(year, end_month, last_day)

    # Start date is first day of quarter
    start_date = date(year, start_month, 1)

    # Previous quarter end date
    if q == 1:
        prev_end_date = date(year - 1, 12, 31)
    else:
        prev_end_month = start_month - 1
        prev_last_day = calendar.monthrange(year, prev_end_month)[1]
        prev_end_date = date(year, prev_end_month, prev_last_day)

    return {
        "start_date": start_date,
        "end_date": end_date,
        "prev_end_date": prev_end_date,
    }


def format_date_german(d: date) -> str:
    """Format date as DD.MM.YYYY."""
    return d.strftime("%d.%m.%Y")


def get_previous_quarter(quarter: str) -> str:
    """Get the previous quarter string."""
    year = int(quarter[:4])
    q = int(quarter[-1])

    if q == 1:
        return f"{year - 1}Q4"
    else:
        return f"{year}Q{q - 1}"


def process_excel(
    excel_path: Path,
    quarter: str,
    meter_reading: float,
    arbeitspreis: float,
    leistungspreis: float,
    co2_abgabe: float,
) -> None:
    """
    Process the Excel file for a new quarter.

    Args:
        excel_path: Path to the Excel file
        quarter: Quarter string like "2025Q4"
        meter_reading: Current meter reading in kWh
        arbeitspreis: Price per MWh in CHF
        leistungspreis: Leistungspreis net amount in CHF
        co2_abgabe: CO2 fee amount in CHF (excl. MwSt.)
    """
    wb = load_workbook(excel_path)

    # Get the previous quarter sheet name
    prev_quarter = get_previous_quarter(quarter)

    # Find the source sheet (previous quarter)
    if prev_quarter not in wb.sheetnames:
        raise ValueError(
            f"Previous quarter sheet '{prev_quarter}' not found in workbook"
        )

    source_sheet = wb[prev_quarter]

    # Copy the sheet
    new_sheet = wb.copy_worksheet(source_sheet)
    new_sheet.title = quarter

    # Move new sheet to be first
    wb.move_sheet(new_sheet, offset=-len(wb.sheetnames) + 1)

    # Calculate dates
    dates = get_quarter_dates(quarter)

    # Update A2: Date range "01.07.2025 - 30.09.2025"
    date_range = f"{format_date_german(dates['start_date'])} - {format_date_german(dates['end_date'])}"
    new_sheet["A2"] = date_range

    # Update A6: "Zählerstand DD.MM.YYYY" (previous quarter end)
    new_sheet["A6"] = f"Zählerstand {format_date_german(dates['prev_end_date'])}"

    # Update A7: "Zählerstand DD.MM.YYYY" (current quarter end)
    new_sheet["A7"] = f"Zählerstand {format_date_german(dates['end_date'])}"

    # Copy D7 to D6 (previous meter reading)
    prev_meter_reading = source_sheet["D7"].value
    new_sheet["D6"] = prev_meter_reading

    # Set D7 to new meter reading
    new_sheet["D7"] = meter_reading

    # Update A13: Date (current quarter end)
    new_sheet["A13"] = format_date_german(dates["end_date"])

    # Update A18: Date (current quarter end)
    new_sheet["A18"] = format_date_german(dates["end_date"])

    # Set C8: Arbeitspreis per MWh
    new_sheet["C8"] = arbeitspreis

    # Set B13: Leistungspreis
    new_sheet["B13"] = leistungspreis

    # Set B18: CO2-Abgabe
    new_sheet["B18"] = co2_abgabe

    # Save the workbook
    wb.save(excel_path)
    wb.close()
