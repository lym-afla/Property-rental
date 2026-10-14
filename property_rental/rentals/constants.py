CURRENCY_CHOICES = (
    ('USD', '$'),
    ('EUR', '€'),
    ('GBP', '£'),
    ('RUB', '₽'),
)

TRANSACTION_CATEGORIES = (
    ('rent', 'Rent'),
    ('tax', 'Tax'),
    ('capex', 'Capex'),
    ('management', 'Management'),
    ('electricity', 'Electricity'),
    ('utilities', 'Utilities'),
    ('internet', 'Internet'),
    ('cost_reimbursement', 'Cost reimbursement'),
    ('other_expenses', 'Other Expenses')
)

INCOME_CATEGORIES = (
    'rent',
)

DEPOSIT_MOVEMENT_KINDS = (
    ("received", "Received"),
    ("returned", "Returned"),
    ("applied", "Applied"),
)

DEPOSIT_APPLICATION_CATEGORIES = ("rent", "cost_reimbursement")
