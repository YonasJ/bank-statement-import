# Copyright 2024 Binhex - Adasat Torres de León.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    plaid_bank_account_id = fields.Many2one(
        related="online_bank_statement_provider_id.plaid_bank_account_id",
        readonly=False,
        string="Plaid Account",
    )
