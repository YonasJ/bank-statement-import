# Copyright 2024 Binhex - Adasat Torres de León.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    plaid_client_id = fields.Char(
        string="Plaid Client ID",
        config_parameter="account_statement_import_online_plaid.plaid_client_id",
    )
    plaid_secret = fields.Char(
        string="Plaid Secret Key",
        config_parameter="account_statement_import_online_plaid.plaid_secret",
    )
    plaid_host = fields.Selection(
        [
            ("sandbox", "Sandbox"),
            ("production", "Production"),
        ],
        default="sandbox",
        string="Plaid Host",
        config_parameter="account_statement_import_online_plaid.plaid_host",
    )
