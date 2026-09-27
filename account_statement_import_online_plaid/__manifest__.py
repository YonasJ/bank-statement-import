# Copyright 2024 Binhex - Adasat Torres de León.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Online Bank Statements: plaid.com",
    "version": "18.0.1.3.0",
    "category": "Account",
    "website": "https://github.com/OCA/bank-statement-import",
    "author": "Binhex, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "installable": True,
    "depends": ["account_statement_import_online"],
    "data": [
        "security/ir.model.access.csv",
        "views/plaid_bank_connection_views.xml",
        "views/res_config_settings_views.xml",
        "views/online_bank_statement_provider.xml",
        "wizards/plaid_account_selector.xml",
        "wizards/online_bank_statement_provider_existing.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "/account_statement_import_online_plaid/static/src/**/*.js",
        ],
    },
    "external_dependencies": {
        "python": ["plaid-python"],
    },
}
