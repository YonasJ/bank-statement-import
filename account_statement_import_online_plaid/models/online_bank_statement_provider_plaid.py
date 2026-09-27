# Copyright 2024 Binhex - Adasat Torres de León.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import logging
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

AVAILABLE_LANGS = [
    "da",
    "nl",
    "en",
    "et",
    "fr",
    "de",
    "hi",
    "it",
    "lv",
    "lt",
    "no",
    "pl",
    "pt",
    "ro",
    "es",
    "sv",
    "vi",
]


class OnlineBankStatementProvider(models.Model):
    _inherit = "online.bank.statement.provider"

    plaid_access_token = fields.Char(copy=False)
    plaid_host = fields.Selection(
        [
            ("sandbox", "Sandbox"),
            ("production", "Production"),
        ],
        string="Plaid Host",
    )
    plaid_connection_id = fields.Many2one(
        "plaid.bank.connection",
        string="Plaid Bank Connection",
    )
    plaid_bank_account_id = fields.Many2one(
        "plaid.bank.account",
        string="Plaid Bank Account",
        domain="[('connection_id', '=', plaid_connection_id)]",
    )
    plaid_account_id = fields.Char(string="Plaid Account ID")
    plaid_account_name = fields.Char(string="Plaid Account Name", readonly=True)
    plaid_account_mask = fields.Char(string="Plaid Account Mask", readonly=True)
    plaid_account_currency = fields.Char(
        string="Plaid Account Currency", readonly=True
    )

    @api.onchange("plaid_connection_id")
    def _onchange_plaid_connection_id(self):
        if (
            self.plaid_bank_account_id
            and self.plaid_bank_account_id.connection_id != self.plaid_connection_id
        ):
            self.plaid_bank_account_id = False
            self.plaid_account_id = False
            self.plaid_account_name = False
            self.plaid_account_mask = False
            self.plaid_account_currency = False

    @api.onchange("plaid_bank_account_id")
    def _onchange_plaid_bank_account_id(self):
        if self.plaid_bank_account_id:
            self.plaid_account_id = self.plaid_bank_account_id.plaid_account_id
            self.plaid_account_name = self.plaid_bank_account_id.name
            self.plaid_account_mask = self.plaid_bank_account_id.mask
            self.plaid_account_currency = self.plaid_bank_account_id.currency_code

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("plaid_bank_account_id"):
                acc = self.env["plaid.bank.account"].browse(vals["plaid_bank_account_id"])
                vals["plaid_account_id"] = acc.plaid_account_id
                vals["plaid_account_name"] = acc.name
                vals["plaid_account_mask"] = acc.mask
                vals["plaid_account_currency"] = acc.currency_code
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("plaid_bank_account_id"):
            acc = self.env["plaid.bank.account"].browse(vals["plaid_bank_account_id"])
            vals["plaid_account_id"] = acc.plaid_account_id
            vals["plaid_account_name"] = acc.name
            vals["plaid_account_mask"] = acc.mask
            vals["plaid_account_currency"] = acc.currency_code
        elif "plaid_bank_account_id" in vals and not vals["plaid_bank_account_id"]:
            vals["plaid_account_id"] = False
            vals["plaid_account_name"] = False
            vals["plaid_account_mask"] = False
            vals["plaid_account_currency"] = False
        return super().write(vals)

    def _get_plaid_client_id(self):
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        return (
            self.username
            or ICP.get_param("account_statement_import_online_plaid.plaid_client_id")
            or self.company_id.plaid_client_id
            or ""
        )

    def _get_plaid_secret(self):
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        return (
            self.password
            or ICP.get_param("account_statement_import_online_plaid.plaid_secret")
            or self.company_id.plaid_secret
            or ""
        )

    def _get_plaid_host(self):
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        return (
            self.plaid_host
            or ICP.get_param("account_statement_import_online_plaid.plaid_host")
            or self.company_id.plaid_host
            or "sandbox"
        )

    def _get_plaid_client(self):
        self.ensure_one()
        client_id = self._get_plaid_client_id()
        secret = self._get_plaid_secret()
        host = self._get_plaid_host()
        if not client_id or not secret:
            raise UserError(
                _(
                    "Plaid Client ID or Secret Key not found. Please configure them in Accounting Settings or on this provider."
                )
            )
        plaid_interface = self.env["plaid.interface"]
        return plaid_interface._client(client_id, secret, host)

    def _obtain_statement_data(self, date_since, date_until):
        self.ensure_one()
        if self.service != "plaid":
            return super()._obtain_statement_data(date_since, date_until)
        return self._plaid_retrieve_data(date_since, date_until), {}

    @api.model
    def _get_available_services(self):
        return super()._get_available_services() + [
            ("plaid", "Plaid.com"),
        ]

    def _country_code(self):
        if self.journal_id.bank_id and self.journal_id.bank_id.country:
            return self.journal_id.bank_id.country.code
        if self.journal_id.company_id.country_id:
            return self.journal_id.company_id.country_id.code
        raise UserError(_("Country code not found for the bank or the company..."))

    def _verify_lang(self, lang):
        if lang not in AVAILABLE_LANGS:
            return "en"
        return lang

    def action_sync_with_plaid(self):
        self.ensure_one()
        plaid_interface = self.env["plaid.interface"]
        client = self._get_plaid_client()
        lang = (
            self.env["res.lang"]._lang_get(self.env.lang or self.env.user.lang).iso_code
        )
        company_name = self.env.company.name

        access_token = (
            self.plaid_connection_id.plaid_access_token
            or self.plaid_access_token
        )
        link_token = plaid_interface._link(
            client=client,
            language=self._verify_lang(lang),
            country_code=self._country_code(),
            company_name=company_name,
            products=["transactions"],
            access_token=access_token or None,
        )
        return {
            "type": "ir.actions.client",
            "tag": "plaid_login",
            "params": {
                "call_model": "online.bank.statement.provider",
                "call_method": "plaid_create_access_token",
                "token": link_token,
                "object_id": self.id,
            },
            "target": "new",
        }

    def _auto_match_plaid_account(self, accounts=None):
        self.ensure_one()
        access_token = (
            self.plaid_connection_id.plaid_access_token
            or self.plaid_access_token
        )
        if not access_token:
            return False
        if accounts is None:
            plaid_interface = self.env["plaid.interface"]
            client = self._get_plaid_client()
            try:
                accounts = plaid_interface._get_accounts(
                    client, access_token
                )
            except Exception as e:
                _logger.warning("Failed to fetch Plaid accounts for matching: %s", e)
                return False
        if not accounts:
            return False

        if len(accounts) == 1:
            acc = accounts[0]
            self.write(
                {
                    "plaid_account_id": acc["account_id"],
                    "plaid_account_name": acc.get("name") or "",
                    "plaid_account_mask": acc.get("mask") or "",
                    "plaid_account_currency": (acc.get("balances") or {}).get(
                        "iso_currency_code"
                    )
                    or "",
                }
            )
            return True

        journal = self.journal_id
        acc_num = (
            journal.bank_account_id.sanitized_acc_number
            or journal.bank_account_id.acc_number
            or ""
        ).strip()
        journal_name = (journal.name or "").strip()
        target_currency = (
            self.currency_id or self.company_id.currency_id
        ).name or ""

        matches = []
        for acc in accounts:
            mask = (acc.get("mask") or "").strip()
            acc_curr = (acc.get("balances") or {}).get("iso_currency_code") or ""
            curr_ok = not target_currency or not acc_curr or (acc_curr == target_currency)
            mask_ok = bool(mask and (mask in acc_num or mask in journal_name))
            if mask_ok and curr_ok:
                matches.append(acc)

        if len(matches) == 1:
            acc = matches[0]
            self.write(
                {
                    "plaid_account_id": acc["account_id"],
                    "plaid_account_name": acc.get("name") or "",
                    "plaid_account_mask": acc.get("mask") or "",
                    "plaid_account_currency": (acc.get("balances") or {}).get(
                        "iso_currency_code"
                    )
                    or "",
                }
            )
            return True

        # If no mask match, try single currency match
        curr_matches = [
            acc
            for acc in accounts
            if (acc.get("balances") or {}).get("iso_currency_code") == target_currency
        ]
        if len(curr_matches) == 1:
            acc = curr_matches[0]
            self.write(
                {
                    "plaid_account_id": acc["account_id"],
                    "plaid_account_name": acc.get("name") or "",
                    "plaid_account_mask": acc.get("mask") or "",
                    "plaid_account_currency": (acc.get("balances") or {}).get(
                        "iso_currency_code"
                    )
                    or "",
                }
            )
            return True

        return False

    def action_select_plaid_account(self):
        self.ensure_one()
        if not self.plaid_access_token:
            raise UserError(_("Please link your Plaid account first."))
        plaid_interface = self.env["plaid.interface"]
        client = self._get_plaid_client()
        accounts = plaid_interface._get_accounts(client, self.plaid_access_token)
        if not accounts:
            raise UserError(_("No accounts returned by Plaid for this connection."))
        lines = []
        for acc in accounts:
            lines.append(
                (
                    0,
                    0,
                    {
                        "account_id": acc["account_id"],
                        "name": acc.get("name") or "",
                        "official_name": acc.get("official_name") or "",
                        "mask": acc.get("mask") or "",
                        "type": str(acc.get("type") or ""),
                        "subtype": str(acc.get("subtype") or ""),
                        "currency": (acc.get("balances") or {}).get(
                            "iso_currency_code"
                        )
                        or "",
                    },
                )
            )
        wizard = self.env["plaid.account.selector.wizard"].create(
            {
                "provider_id": self.id,
                "line_ids": lines,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Select Plaid Account for %s") % self.journal_id.display_name,
            "res_model": "plaid.account.selector.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_link_existing_plaid(self):
        self.ensure_one()
        existing_providers = self.search(
            [
                ("service", "=", "plaid"),
                ("plaid_access_token", "!=", False),
                ("id", "!=", self.id),
            ]
        )
        if not existing_providers:
            raise UserError(
                _(
                    "No existing Plaid connection found. Please click 'Sync with Plaid.com' first."
                )
            )
        wizard = self.env["online.bank.statement.provider.existing.plaid"].create(
            {
                "provider_id": self.id,
                "other_provider_id": existing_providers[0].id,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Link Existing Plaid Connection"),
            "res_model": "online.bank.statement.provider.existing.plaid",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def _plaid_retrieve_data(self, date_since, date_until):
        access_token = (
            self.plaid_connection_id.plaid_access_token
            or self.plaid_access_token
        )
        if not access_token:
            raise UserError(
                _(
                    "Please link your Plaid connection or provider first by "
                    "selecting a Plaid Bank Connection or clicking 'Sync with Plaid'."
                )
            )
        account_id = (
            self.plaid_bank_account_id.plaid_account_id
            or self.plaid_account_id
        )
        if not account_id and not self.plaid_bank_account_id:
            self._auto_match_plaid_account()
            account_id = self.plaid_account_id
        if not account_id:
            raise UserError(
                _(
                    "Please select a Plaid account for journal '%s'."
                )
                % self.journal_id.display_name
            )
        plaid_interface = self.env["plaid.interface"]
        client = self._get_plaid_client()
        transactions = plaid_interface._get_transactions(
            client,
            access_token,
            date_since,
            date_until,
            account_ids=[account_id],
        )
        # Extra safety check: ensure transactions belong to this account
        transactions = [
            t for t in transactions if t.get("account_id") == account_id
        ]
        return self._prepare_vals_for_statement(transactions)

    @api.model
    def plaid_create_access_token(self, public_token, active_id):
        provider = self.browse(active_id)
        if public_token:
            client = provider._get_plaid_client()
            plaid_interface = self.env["plaid.interface"]
            try:
                args = [client, public_token]
                provider.plaid_access_token = plaid_interface._login(*args)
            except Exception as e:
                _logger.info("Public token exchange in update mode: %s", e)
        if provider.plaid_access_token:
            if not provider.plaid_account_id:
                provider._auto_match_plaid_account()
            return True
        return False

    def _prepare_vals_for_statement(self, transactions):
        return [
            {
                "date": transaction["date"],
                "ref": transaction["name"],
                "payment_ref": transaction["name"],
                "unique_import_id": transaction["transaction_id"],
                "amount": float(transaction["amount"]) * -1.00,
                "raw_data": transaction,
            }
            for transaction in transactions
        ]
