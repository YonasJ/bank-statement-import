# Copyright 2024 Binhex - Adasat Torres de León.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    plaid_bank_account_id = fields.Many2one(
        related="online_bank_statement_provider_id.plaid_bank_account_id",
        readonly=False,
        string="Plaid Account",
    )
    plaid_interval_number = fields.Integer(
        related="online_bank_statement_provider_id.interval_number",
        readonly=False,
        string="Scheduled update interval",
    )
    plaid_interval_type = fields.Selection(
        related="online_bank_statement_provider_id.interval_type",
        readonly=False,
        string="Interval Unit",
    )
    plaid_next_run = fields.Datetime(
        related="online_bank_statement_provider_id.next_run",
        readonly=False,
        string="Next scheduled pull",
    )
    plaid_statement_creation_mode = fields.Selection(
        related="online_bank_statement_provider_id.statement_creation_mode",
        readonly=False,
        string="Transactions interval to obtain",
    )
    plaid_create_statement = fields.Boolean(
        related="online_bank_statement_provider_id.create_statement",
        readonly=False,
        string="Create Statement?",
    )
    plaid_tz = fields.Selection(
        related="online_bank_statement_provider_id.tz",
        readonly=False,
        string="Timezone",
    )

    @api.onchange("online_bank_statement_provider", "bank_statements_source")
    def _onchange_online_bank_statement_provider_plaid(self):
        if (
            self.bank_statements_source == "online"
            and self.online_bank_statement_provider == "plaid"
            and not self.online_bank_statement_provider_id
            and self._origin.id
        ):
            self._update_providers()

    def write(self, vals):
        plaid_field_keys = {
            "plaid_bank_account_id",
            "plaid_interval_number",
            "plaid_interval_type",
            "plaid_next_run",
            "plaid_statement_creation_mode",
            "plaid_create_statement",
            "plaid_tz",
        }
        if any(k in vals for k in plaid_field_keys) or vals.get(
            "online_bank_statement_provider"
        ) == "plaid":
            for journal in self:
                if not journal.online_bank_statement_provider_id and (
                    journal.online_bank_statement_provider == "plaid"
                    or vals.get("online_bank_statement_provider") == "plaid"
                ):
                    journal._update_providers()
        return super().write(vals)
