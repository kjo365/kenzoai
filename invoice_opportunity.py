#!/usr/bin/env python3
"""Invoice Opportunity: local CSV audit and fixed-fee proposal generator.

Python 3.10+, standard library only. See README.md for input and assumptions.
"""
import argparse
import csv
import io
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

PENNY = Decimal('0.01')
REQUIRED = {'invoice_id', 'client', 'due_date', 'amount', 'paid', 'currency'}


def money(value):
    return f'£{value:,.2f}'


def decimal_amount(raw):
    try:
        value = Decimal(raw.strip())
    except InvalidOperation as exc:
        raise ValueError('amount must be a plain decimal number') from exc
    if not value.is_finite() or value < 0 or value > Decimal('1000000000000'):
        raise ValueError('amount must be finite, nonnegative and at most 1 trillion')
    if value != value.quantize(PENNY):
        raise ValueError('amount must have at most two decimal places')
    return value


def safe_text(raw):
    return re.sub(r'[\r\n\t|`<>]', ' ', str(raw)).strip()


def spreadsheet_safe(raw):
    text = str(raw)
    if text.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + text
    return text


def load_invoices(path, as_of):
    valid, errors = [], []
    with path.open(encoding='utf-8-sig', newline='') as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError('CSV headers are missing or repeated')
        missing = REQUIRED - set(reader.fieldnames)
        if missing:
            raise ValueError('Missing CSV columns: ' + ', '.join(sorted(missing)))
        raw_rows = list(reader)
    counts = Counter((row.get('invoice_id') or '').strip() for row in raw_rows)
    for number, row in enumerate(raw_rows, 2):
        try:
            if None in row or any(row.get(key) is None for key in REQUIRED):
                raise ValueError('row has the wrong number of fields')
            invoice_id = row['invoice_id'].strip()
            client = row['client'].strip()
            if not invoice_id or not client:
                raise ValueError('invoice_id and client are required')
            if counts[invoice_id] > 1:
                raise ValueError(f'duplicate invoice_id {invoice_id!r}; all copies excluded')
            if row['currency'].strip().upper() != 'GBP':
                raise ValueError('only GBP is supported; no currency conversion performed')
            amount = decimal_amount(row['amount'])
            paid = decimal_amount(row['paid'])
            if paid > amount:
                raise ValueError('paid exceeds amount; review credit/overpayment separately')
            due = date.fromisoformat(row['due_date'].strip())
            valid.append(dict(invoice_id=invoice_id, client=client, due_date=due,
                              outstanding=amount-paid, days_overdue=max(0, (as_of-due).days)))
        except ValueError as exc:
            errors.append(f'CSV row {number}: {exc}')
    return valid, errors


def analyse(rows, fee, recovery_percent):
    overdue = sorted((r for r in rows if r['outstanding'] > 0 and r['days_overdue'] > 0),
                     key=lambda r: (-r['outstanding'], -r['days_overdue'], r['invoice_id']))
    total = sum((r['outstanding'] for r in overdue), Decimal(0))
    buckets = {label: Decimal(0) for label in ('1–30 days', '31–60 days', '61–90 days', '91+ days')}
    for row in overdue:
        days = row['days_overdue']
        label = '1–30 days' if days <= 30 else '31–60 days' if days <= 60 else '61–90 days' if days <= 90 else '91+ days'
        buckets[label] += row['outstanding']
    scenario = (total * recovery_percent / 100).quantize(PENNY, rounding=ROUND_HALF_UP)
    return overdue, total, buckets, scenario


def audit_report(rows, errors, as_of, fee, recovery_percent):
    overdue, total, buckets, scenario = analyse(rows, fee, recovery_percent)
    outstanding = sum((r['outstanding'] for r in rows), Decimal(0))
    lines = ['# Invoice opportunity report', '', f'As of: {as_of.isoformat()}', '',
             f'Valid invoices: {len(rows)}. Excluded rows: {len(errors)}.',
             f'Total outstanding: {money(outstanding)}. Overdue: {money(total)}.', '',
             'Overdue balances are existing receivables, not new revenue or guaranteed collections.',
             'The report assumes each CSV record describes one invoice with cumulative payments.', '',
             '## Ageing', '', '| Age | Overdue balance |', '|---|---:|']
    lines += [f'| {label} | {money(value)} |' for label, value in buckets.items()]
    lines += ['', '## Follow-up queue', '',
              'Sorted by outstanding balance, then age. This is not a prediction of payment likelihood.', '',
              '| Invoice | Client | Days overdue | Outstanding |', '|---|---|---:|---:|']
    lines += [f"| {safe_text(r['invoice_id'])} | {safe_text(r['client'])} | {r['days_overdue']} | {money(r['outstanding'])} |" for r in overdue]
    if not overdue:
        lines.append('| — | No overdue invoices | — | £0.00 |')
    lines += ['', '## Explicit scenario, not a forecast', '',
              f'Assumed incremental collection: {recovery_percent}% of overdue balances = {money(scenario)}.',
              f'Proposed service fee: {money(fee)}. Scenario cash collected minus fee: {money(scenario-fee)}.',
              'This excludes other costs, tax, timing, disputes, and amounts that would be paid without the service.']
    if total:
        lines.append(f'Collections equal to the fee would require {fee / total * 100:.2f}% of overdue balances.')
    else:
        lines.append('No overdue balance supports a collections-based fee comparison.')
    lines += ['', '## Data issues to resolve before acting', '']
    lines += ['- ' + safe_text(error) for error in errors] or ['No row validation issues found.']
    lines += ['', '## Before contacting a customer', '',
              'Confirm the balance, payment history, due date, disputes and authority to follow up.',
              'No messages or payment requests have been sent.']
    return '\n'.join(lines) + '\n', overdue


def proposal(business, fee):
    return f'''# Draft service proposal — {safe_text(business)}

## Offer: receivables reporting setup

Fixed fee: {money(fee)}. Tax treatment and payment terms to be agreed before acceptance.
Proposed delivery: five business days after receiving complete, authorised data.
Only offer this scope if you can deliver it; this draft does not establish customer demand.

Deliverables:
- Validate one GBP invoice export and identify data exceptions.
- Produce an outstanding-balance report and ageing summary.
- Provide a prioritised invoice review queue and customer-specific follow-up drafts.
- Hand over the reusable script and explain how to refresh the report.
- Include one review call and one correction pass for the agreed export.

Acceptance: totals reconciled with the client's source export, exceptions documented,
and the client can rerun the report. Additional integrations require a separate scope.
No collection, accounting, legal, tax or investment advice is included.
No promise of collection success or revenue increase is made.

## Outreach draft for manual review

Hello,

I offer a fixed-fee receivables reporting setup for {money(fee)}. It turns an
authorised invoice export into an ageing report, a data-exception list and a
repeatable follow-up queue. Would a short discussion help establish whether
that solves a current reporting problem for {safe_text(business)}?

If so, we can agree scope, data handling, delivery date and payment terms before work begins.

## Five-minute preparation checklist

1. Choose one business whose reporting problem you understand.
2. Run the demo and inspect the sample outputs.
3. Confirm you can deliver the stated service and adjust the fee/scope.
4. Personalise the draft with verified context; review it before sending yourself.
5. Ask for a discovery conversation. A sale and payment can take much longer.

One accepted {money(fee)} engagement is gross booked revenue; only payment is cash
received. Profit also depends on delivery costs, fees and taxes.
'''


def followups(overdue, as_of):
    groups = defaultdict(list)
    for row in overdue:
        groups[row['client']].append(row)
    lines = ['# Follow-up drafts — review before sending', '', 'Confirm all balances and disputes first. Nothing has been sent.', '']
    for client, items in sorted(groups.items()):
        total = sum((r['outstanding'] for r in items), Decimal(0))
        lines += [f'## {safe_text(client)}', '', f'Hello {safe_text(client)},', '',
                  f'Our invoice report as of {as_of} shows the following open balances:', '']
        lines += [f"- {safe_text(r['invoice_id'])}: {money(r['outstanding'])}, due {r['due_date']}." for r in items]
        lines += ['', f'Total: {money(total)}. Could you confirm whether these match your records and advise on expected payment timing? If paid or disputed, please let us know so we can update the records.', '']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path, help='GBP invoice export')
    parser.add_argument('--as-of', type=date.fromisoformat, default=date.today())
    parser.add_argument('--business', default='your business')
    parser.add_argument('--fee', type=decimal_amount, default=Decimal('1000'))
    parser.add_argument('--recovery-percent', type=decimal_amount, default=Decimal('0'),
                        help='explicit hypothetical incremental collection percentage; default 0')
    parser.add_argument('--out', type=Path, default=Path('invoice-output'))
    args = parser.parse_args()
    if args.fee <= 0 or args.recovery_percent > 100:
        parser.error('fee must be positive; recovery-percent must be between 0 and 100')
    try:
        rows, errors = load_invoices(args.csv, args.as_of)
        if not rows:
            raise ValueError('No valid invoice rows. ' + '; '.join(errors[:5]))
        report, overdue = audit_report(rows, errors, args.as_of, args.fee, args.recovery_percent)
        queue = io.StringIO(newline='')
        writer = csv.writer(queue)
        writer.writerow(['invoice_id', 'client', 'due_date', 'days_overdue', 'outstanding_gbp'])
        for row in overdue:
            writer.writerow([spreadsheet_safe(row['invoice_id']), spreadsheet_safe(row['client']),
                             row['due_date'], row['days_overdue'], f"{row['outstanding']:.2f}"])
        outputs = {'report.md': report, 'proposal.md': proposal(args.business, args.fee),
                   'followups.md': followups(overdue, args.as_of), 'queue.csv': queue.getvalue()}
        args.out.mkdir(parents=True, exist_ok=True)
        if any((args.out / name).exists() for name in outputs):
            raise ValueError('Output files already exist; choose another --out directory')
        for name, content in outputs.items():
            with (args.out / name).open('x', encoding='utf-8', newline='') as target:
                target.write(content)
        print(f'Created {len(outputs)} files in {args.out.resolve()}')
        print(f'{len(rows)} valid invoices; {len(errors)} excluded rows. Review report.md before use.')
        print('No sales, collections, messages or payments performed.')
    except (OSError, ValueError, csv.Error) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
