import pdfplumber
import re


def parse_purification_pdf(pdf_path, period, effective_from, effective_to=None, source_document=None):
    """
    Parse a KMI recomposition PDF and extract purification ratios.
    Returns a list of dicts with symbol and ratio.
    """
    results = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if not table:
                continue

            for row in table:
                if not row or len(row) < 7:
                    continue

                # Skip header rows
                ticker = row[1]
                if not ticker or ticker in ['Ticker', 'No.', '']:
                    continue

                # Clean ticker
                ticker = ticker.strip()
                if not ticker or len(ticker) > 15:
                    continue

                # Get final shariah status (last column)
                status = row[-1]
                if not status:
                    continue
                status = status.strip()

                # Skip non-compliant
                if 'Non-Compliant' in status or 'NC' in status:
                    continue

                # Get income ratio / purification rate (column index 4)
                income_ratio_raw = row[6] if len(row) > 6 else None

                ratio = None
                if income_ratio_raw:
                    income_ratio_raw = income_ratio_raw.strip()
                    # N/A means Islamic institution - pure by nature
                    if income_ratio_raw == 'N/A':
                        ratio = None  # null = no purification needed
                    else:
                        # Extract percentage number e.g. "0.42%" or "4.52%"
                        match = re.search(r'(\d+\.?\d*)', income_ratio_raw)
                        if match:
                            ratio = float(match.group(1))
                        # If 0.00% - no purification needed
                        if ratio == 0.0:
                            ratio = None

                results.append({
                    'symbol': ticker,
                    'ratio': ratio,
                    'period': period,
                    'effective_from': effective_from,
                    'effective_to': effective_to,
                    'source_document': source_document or pdf_path,
                })



    return results


if __name__ == "__main__":
    # Test with SinceDec25.pdf
    results = parse_purification_pdf(
        pdf_path="SinceDec25.pdf",
        period="H1-2025",
        effective_from="2025-12-02",
        effective_to=None,
        source_document="KMI Recomp H1-2025 (Dec 2025)"
    )

    print(f"Total records parsed: {len(results)}")
    print("\nSample (first 10):")
    for r in results[:10]:
        print(r)

    # Check MEBL specifically
    mebl = [r for r in results if r['symbol'] == 'MEBL']
    print(f"\nMEBL: {mebl}")

    # Check LUCK
    luck = [r for r in results if r['symbol'] == 'LUCK']
    print(f"LUCK: {luck}")

    # Stats
    with_ratio = [r for r in results if r['ratio'] is not None]
    without_ratio = [r for r in results if r['ratio'] is None]
    print(f"\nWith purification ratio: {len(with_ratio)}")
    print(f"No purification needed (Islamic/zero): {len(without_ratio)}")

