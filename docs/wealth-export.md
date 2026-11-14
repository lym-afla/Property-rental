# Exporting Rent history to Wealth

After applying Rent's migrations, run the command as the application's environment user:

```sh
uv run python property_rental/manage.py export_wealth --out /secure/path/rent.json --subject '<authentik sub>'
```

The subject must match an existing `OIDCIdentity`. Add `--issuer '<issuer URL>'` when the same subject occurs under multiple issuers. Ownership is resolved through that identity; there is no fallback to usernames or emails. Only that user's owned properties and their financial records are included. Tenant names, contacts, transaction comments, loan account references and addresses are omitted.

The file uses Wealth v1.1 and contains all stored transactions, loans and dated capital history. `--as-of YYYY-MM-DD` selects the arrears and deposit snapshot date (default: today); it does not trim stored history. Arrears use Rent's existing rent schedule and grace rules, summing each tenant's positive amount owed; tenant credits do not cancel another tenant's arrears. Snapshot facts have property/date IDs. Each fact has a SHA-256 content version, excluding timestamps, and an actual source `updated_at` (maximum contributing row timestamp for derived facts). Changing only timestamps leaves the content version unchanged. Historical rows receive migration-time timestamps; earlier modification times cannot be recovered.

Valuation and debt observations can be recorded independently. The export carries each known field forward from its last observation, without interpolation or backward filling. The first observation must establish both value and debt explicitly, including a recorded zero for a debt-free property. Complementary rows on the same date form one snapshot because Wealth allows only one snapshot per property/date. Conflicting same-date balances, multiple simultaneous loan balances, missing observations, unknown initial values/debts and currency mismatches stop the export with an error before replacing the output. Supply the missing facts in Rent rather than guessing. Wealth v1.1 cannot represent several concurrent loan balances for a property on the same date; those require a contract extension. Property compatibility fields match the last exported observation.

Costs are exported as positive `cost` amounts; reimbursements are positive `cost_reimbursement`. Loan interest and principal have distinct types and loan IDs. Security-deposit receipts become `deposit_in`; returns become `deposit_out`. An application becomes a `deposit_out` plus its existing linked rent/reimbursement transaction, once. These offset on the bank side and release the deposit liability without inventing a second cash receipt. An invalid or missing application link stops the export. Deposits are also exported as one property-level balance at the snapshot date.

Migration-created loan lenders are `UNKNOWN — fill in`. The command lists their loan/property IDs, without tenant information. This is a reminder to replace placeholders with the actual lender; rates, payment history and other unknown facts are never inferred. The export does not change them.

## Life OS: read-only Postgres access

An administrator can create a dedicated role; **these are instructions, not actions performed by the export**. Substitute the database and schema names. Set a password through the normal secret-management process, not shell history.

```sql
CREATE ROLE rent_readonly LOGIN;
GRANT CONNECT ON DATABASE rent TO rent_readonly;
GRANT USAGE ON SCHEMA public TO rent_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO rent_readonly;
-- Run as the role that owns tables, so future migrations retain read access:
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO rent_readonly;
ALTER ROLE rent_readonly SET default_transaction_read_only = on;
```

Configure the normal production database settings with this read-only role using the deployment's secret configuration and run only `export_wealth`, not migrations. No table/sequence write privileges are required. Export tests wrap database execution and reject every statement other than `SELECT`. The output is a financial file: place it in a directory with appropriate access restrictions.

## Parser validation

Once Wealth v1.1 is on its main branch, validate the file from `/home/yl/code/Wealth-statements/backend`:

```sh
uv run python -c "from pathlib import Path; from wealth.connectors.files import parse_file; parse_file('rent', Path('/secure/path/rent.json').read_bytes()); print('ok')"
```

This reads the file through Wealth's strict schema and reference checks. It does not import data or modify Wealth. Parser availability in a local feature checkout alone does not establish that v1.1 has been merged to main.

## Recording mortgage history

Open a property's **Loans** tab to create loans, replace placeholder lenders and record payments.
Enter total plus interest, or interest plus principal. Both rows save together in the loan currency.
Interest is a cost; principal is a balance-sheet outflow and appears only in net cash flow.
Leave debt blank for a valuation-only observation; enter an explicit zero when paying off debt.
Record payoff observations with the relevant loan. An unlinked zero can close the sole observed outstanding loan; ambiguous payoffs require a loan link.
Reconciliation checks each consecutive pair using principal dated after opening through closing, inclusive.
An absolute difference above 1 unit flags a warning; the check does not infer advances, fees or missing history.

For bulk history, prepare a UTF-8 CSV with these headers:

```csv
date,total,interest,comment
```

Alternatively use `date,interest,principal,comment`. `comment` and `period` are optional.
Use ISO dates and nonnegative decimals with at most two decimal places; supply exactly one split mode per row.
Use your own recorded amounts. Preview first:

```sh
uv run python property_rental/manage.py import_loan_payments --loan <id> --file /path/payments.csv --dry-run
uv run python property_rental/manage.py import_loan_payments --loan <id> --file /path/payments.csv
```

The importer validates every row before writing, saves the file atomically, and rejects duplicate payment components.
If a matching component already exists, review the ledger before importing. This command requires write access;
`export_wealth` works with the read-only role above.
