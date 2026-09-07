# Invoice Opportunity

A local Python tool for preparing a fixed-fee receivables reporting service.
It does not earn money automatically, source buyers, verify market demand or guarantee a £1,000 sale.
Five minutes can prepare an offer; selling and delivering it takes additional work.

## Run the fictional demo

Requires Python 3.10 or newer. No packages, API keys or accounts required.

```bash
python3 invoice_opportunity.py sample_invoices.csv --as-of 2026-09-07 --business "Example Studio" --out demo-output
```

On Windows, use `python` if `python3` is unavailable.
Open `demo-output/report.md`, `queue.csv`, `proposal.md` and `followups.md`.
The sample contains £9,500 overdue, £11,500 total outstanding and two excluded duplicate rows.
All businesses and balances in the sample are fictional.

## Use your own authorised export

```bash
python3 invoice_opportunity.py invoices.csv --business "Client name" --fee 1000 --out client-output
```

Required exact headers: `invoice_id,client,due_date,amount,paid,currency`.
Dates use YYYY-MM-DD. Amount and paid are nonnegative plain decimal numbers
with at most two decimal places. Paid means cumulative amount paid against
that invoice, not a yes/no flag. One row per unique invoice ID; currency must be GBP.
Do not mix businesses whose invoice IDs overlap. Fully paid and not-yet-due
invoices are excluded from the overdue queue. Due today is not yet overdue.

Duplicate IDs are excluded in their entirety to avoid silently double-counting.
Invalid rows, non-GBP currencies and overpayments are excluded and reported.
Credit notes and currency conversion are not implemented. Reconcile exclusions
against your accounting records before using totals. If all rows fail, the tool stops.

`--as-of` defaults to the computer's local date. `--recovery-percent 20` optionally
models an explicitly hypothetical incremental collection scenario; the default
is 0%, not a prediction. Collections are existing receivables, not new revenue.
Scenario cash minus service fee is not profit or a complete ROI calculation.

## Business workflow

1. Confirm a prospective client has a reporting problem and willingness to pay.
2. Agree scope and obtain an authorised export through an agreed secure process.
3. Audit it, resolve data exceptions and reconcile totals with the client.
4. Deliver the report, refresh instructions and reviewed follow-up drafts.

The £1,000 proposal is editable and assumes you can provide the described service.
Demand has not been researched or validated. No automated outreach, scraping,
trading, accounting-system integration or payment collection is included.
Only manually send drafts after reviewing their factual accuracy and your authority.

Processing is local; the program makes no network requests. Reports contain
client information. Store and share them appropriately and do not commit real
invoice exports or generated reports to a public GitHub repository.
Choose a new `--out` directory for every run; existing outputs are never overwritten.

## GitHub

Commit this script, README and fictional sample to the repository you select.
The included `.gitignore` excludes common input and output names. It is not a
substitute for reviewing every file before committing.
