# Mortgage products within a continuous loan history

The owner wants each historical mortgage product filed separately, rather than one rate representing every payment. The property Loans page must show editable dated products, including variable trackers and temporary standard-rate periods. Historical uncertainty must remain visible.

Keep Loan as the existing continuous accounting record and introduce LoanProduct metadata beneath it. Creating unrelated loans for every rate switch would split the already reconciled principal/fee history and change Wealth loan identities. Keeping rates only in payment comments does not satisfy separate product inputs. Product records preserve the financial history while providing the requested distinct entries.

LoanProduct fields: loan, name, lender, start_date, nullable end_date, nullable interest_rate, rate_type (empty/fixed/variable), nullable opening_balance, notes, timestamps. Rates are initial product rates; tracker changes belong in notes until an explicit rate schedule is required. Dates are inclusive and products of the same loan cannot overlap. Unknown rates remain empty. Product dates may precede the legacy Loan start_date, which currently describes the recorded current product.

Owner-scoped REST CRUD at /api/v1/loan-products/, filtered by loan or property. Read-only identity/timestamps; no parent change after creation. Positive bounded integer filters, nonnegative finite amounts/rates, valid dates and same-loan overlap validation. Product edits never create, move or delete payment, fee or balance records. Existing Loan API and Wealth v1.1 identifiers/payloads remain compatible.

A generic migration copies each existing Loan's recorded terms into one initial product. The production-specific population is a separate backed-up, guarded data operation using private source evidence, never hardcoded financial data in a migration. The owner has supplied all available evidence; retain estimated dates/rates and unknown original Halifax product details explicitly.

The Loans page displays product names, lenders, rates, periods, opening balances and source notes, with add/edit/delete controls and confirmation for deletion. Existing payment, fee and reconciliation controls remain on the continuous loan. Product listings are chronological. Current product terms are kept in the legacy Loan API for compatibility; separate product records are the history presented by the new UI.

Use existing Django/DRF/React/query/form components; no dependency or transport changes. Version 2.5.0, synchronized in all required files. Verify ownership, overlap boundaries, migration backfill, CRUD, visible distinct products, and financial/export invariance. Deploy through the established app-only Life OS release path, populate records after a backup, and verify actual production data and frontend output.
