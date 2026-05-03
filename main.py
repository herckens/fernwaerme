"""Fernwärme invoice processor - main entry point."""

import sys
from pathlib import Path

from invoice_extractor import extract_invoice_data, InvoiceData
from excel_processor import process_excel, quarter_to_sheet_name


def get_user_input() -> tuple[str, float]:
    """
    Get quarter and meter reading from user.

    Returns:
        Tuple of (quarter string, meter reading)
    """
    print("\n=== Fernwärme Invoice Processor ===\n")

    # Get quarter
    while True:
        quarter = input("Enter quarter (e.g., 2025Q4): ").strip().upper()
        if (
            len(quarter) == 6
            and quarter[:4].isdigit()
            and quarter[4] == "Q"
            and quarter[5] in "1234"
        ):
            break
        print("Invalid format. Please use format like '2025Q4'")

    # Get meter reading
    while True:
        try:
            reading_str = input("Enter current meter reading (kWh): ").strip()
            meter_reading = float(reading_str.replace(",", "."))
            break
        except ValueError:
            print("Invalid number. Please enter a valid meter reading.")

    return quarter, meter_reading


def prompt_for_value(name: str, unit: str) -> float:
    """Prompt user to manually enter a value."""
    while True:
        try:
            value_str = input(f"Enter {name} ({unit}): ").strip()
            return float(value_str.replace(",", "."))
        except ValueError:
            print("Invalid number. Please try again.")


def confirm_values(
    data: InvoiceData, meter_reading: float
) -> tuple[float, float, float]:
    """
    Show extracted values and confirm or correct them.

    Returns:
        Tuple of (arbeitspreis, leistungspreis, co2_abgabe)
    """
    print("\n=== Extracted Values ===\n")

    # Arbeitspreis
    if data.arbeitspreis is not None:
        print(f"Arbeitspreis (per MWh): {data.arbeitspreis:.2f} CHF")
        confirm = input("Correct? [Y/n]: ").strip().lower()
        if confirm == "n":
            arbeitspreis = prompt_for_value("Arbeitspreis", "CHF per MWh")
        else:
            arbeitspreis = data.arbeitspreis
    else:
        print("Arbeitspreis: Could not extract")
        arbeitspreis = prompt_for_value("Arbeitspreis", "CHF per MWh")

    # Leistungspreis
    if data.leistungspreis is not None:
        print(f"Leistungspreis (Preis pro Monat): {data.leistungspreis:.2f} CHF")
        confirm = input("Correct? [Y/n]: ").strip().lower()
        if confirm == "n":
            leistungspreis = prompt_for_value("Leistungspreis", "CHF")
        else:
            leistungspreis = data.leistungspreis
    else:
        print("Leistungspreis: Could not extract")
        leistungspreis = prompt_for_value("Leistungspreis", "CHF")

    # CO2-Abgabe
    if data.co2_abgabe is not None:
        print(f"CO2-Abgabe (excl. MwSt.): {data.co2_abgabe:.2f} CHF")
        confirm = input("Correct? [Y/n]: ").strip().lower()
        if confirm == "n":
            co2_abgabe = prompt_for_value("CO2-Abgabe", "CHF")
        else:
            co2_abgabe = data.co2_abgabe
    else:
        print("CO2-Abgabe: Could not extract")
        co2_abgabe = prompt_for_value("CO2-Abgabe", "CHF")

    print(f"\nMeter reading: {meter_reading:.3f} kWh")

    return arbeitspreis, leistungspreis, co2_abgabe


def main():
    """Main entry point."""
    # Get user input
    quarter, meter_reading = get_user_input()

    # Check for invoice file
    input_dir = Path("input")
    pdf_path = input_dir / f"Rechnung_{quarter}.pdf"

    if not pdf_path.exists():
        print(f"\nError: Invoice file not found: {pdf_path}")
        print(f"Please place the invoice PDF at: {pdf_path.absolute()}")
        sys.exit(1)

    print(f"\nProcessing invoice: {pdf_path}")

    # Extract data from invoice
    print("Extracting data from invoice (this may take a moment)...")
    invoice_data = extract_invoice_data(pdf_path)

    # Confirm values with user
    arbeitspreis, leistungspreis, co2_abgabe = confirm_values(
        invoice_data, meter_reading
    )

    # Final confirmation
    print("\n=== Summary ===")
    print(f"Quarter: {quarter}")
    print(f"Meter reading: {meter_reading:.3f} kWh")
    print(f"Arbeitspreis: {arbeitspreis:.2f} CHF/MWh")
    print(f"Leistungspreis: {leistungspreis:.2f} CHF/Monat")
    print(f"CO2-Abgabe: {co2_abgabe:.2f} CHF")

    confirm = input("\nProceed with Excel update? [Y/n]: ").strip().lower()
    if confirm == "n":
        print("Aborted.")
        sys.exit(0)

    # Process Excel
    excel_path = Path("output") / "Fernwaerme Abrechnung.xlsx"

    if not excel_path.exists():
        print(f"\nError: Excel file not found: {excel_path}")
        sys.exit(1)

    print(f"\nUpdating Excel file: {excel_path}")

    # Check if sheet already exists
    from openpyxl import load_workbook

    sheet_name = quarter_to_sheet_name(quarter)
    wb = load_workbook(excel_path)
    overwrite = False
    if sheet_name in wb.sheetnames:
        confirm = (
            input(f"\nSheet '{sheet_name}' already exists. Overwrite? [y/N]: ")
            .strip()
            .lower()
        )
        if confirm != "y":
            print("Aborted.")
            wb.close()
            sys.exit(0)
        overwrite = True
    wb.close()

    try:
        process_excel(
            excel_path=excel_path,
            quarter=quarter,
            meter_reading=meter_reading,
            arbeitspreis=arbeitspreis,
            leistungspreis=leistungspreis,
            co2_abgabe=co2_abgabe,
            overwrite=overwrite,
        )
        print(f"\nSuccess! Sheet '{sheet_name}' has been created and populated.")
    except Exception as e:
        print(f"\nError updating Excel: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
