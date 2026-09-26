# Copyright 2024 Binhex - Adasat Torres de León.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    plaid_client_id = fields.Char(
        related="company_id.plaid_client_id",
        readonly=False,
        string="Plaid Client ID",
    )
    plaid_secret = fields.Char(
        related="company_id.plaid_secret",
        readonly=False,
        string="Plaid Secret Key",
    )
    plaid_host = fields.Selection(
        related="company_id.plaid_host",
        readonly=False,
        string="Plaid Host",
    )
