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
        default="sandbox",
    )
    plaid_account_id = fields.Char(string="Plaid Account ID")
    plaid_account_name = fields.Char(string="Plaid Account Name", readonly=True)
    plaid_account_mask = fields.Char(string="Plaid Account Mask", readonly=True)
    plaid_account_currency = fields.Char(
        string="Plaid Account Currency", readonly=True
    )

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
        args = [self.username, self.password, self.plaid_host]
        client = plaid_interface._client(*args)
        lang = (
            self.env["res.lang"]._lang_get(self.env.lang or self.env.user.lang).iso_code
        )
        company_name = self.env.company.name

        link_token = plaid_interface._link(
            client=client,
            language=self._verify_lang(lang),
            country_code=self._country_code(),
            company_name=company_name,
            products=["transactions"],
            access_token=self.plaid_access_token or None,
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
        if not self.plaid_access_token:
            return False
        if accounts is None:
            plaid_interface = self.env["plaid.interface"]
            client = plaid_interface._client(
                self.username, self.password, self.plaid_host
            )
            try:
                accounts = plaid_interface._get_accounts(
                    client, self.plaid_access_token
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
        client = plaid_interface._client(
            self.username, self.password, self.plaid_host
        )
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
        if not self.plaid_access_token:
            raise UserError(
                _(
                    "Please link your Plaid account first by "
                    "clicking on 'Sync with Plaid'."
                )
            )
        if not self.plaid_account_id:
            self._auto_match_plaid_account()
        if not self.plaid_account_id:
            raise UserError(
                _(
                    "Please select a Plaid account for journal '%s' by clicking 'Select Plaid Account'."
                )
                % self.journal_id.display_name
            )
        plaid_interface = self.env["plaid.interface"]
        args = [self.username, self.password, self.plaid_host]
        client = plaid_interface._client(*args)
        transactions = plaid_interface._get_transactions(
            client,
            self.plaid_access_token,
            date_since,
            date_until,
            account_ids=[self.plaid_account_id] if self.plaid_account_id else None,
        )
        # Extra safety check: ensure transactions belong to this account
        if self.plaid_account_id:
            transactions = [
                t for t in transactions if t.get("account_id") == self.plaid_account_id
            ]
        return self._prepare_vals_for_statement(transactions)

    @api.model
    def plaid_create_access_token(self, public_token, active_id):
        provider = self.browse(active_id)
        if public_token:
            plaid_interface = self.env["plaid.interface"]
            client = plaid_interface._client(
                provider.username, provider.password, provider.plaid_host
            )
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
