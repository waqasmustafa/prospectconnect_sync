# prospectconnect_sync/models/res_config_settings.py
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # API configuration
    pc_api_key = fields.Char(
        string="ProspectConnect API Key",
        config_parameter="prospectconnect_sync.api_key",
    )
    pc_base_url = fields.Char(
        string="Base URL",
        config_parameter="prospectconnect_sync.base_url",
        default="https://api.prospectconnect.ai",
    )

    # Sync behaviour
    pc_sync_direction = fields.Selection(
        [
            ("odoo_to_pc", "Odoo → ProspectConnect"),
            ("pc_to_odoo", "ProspectConnect → Odoo"),
            ("bidirectional", "Bi-directional"),
        ],
        string="Sync Direction",
        default="bidirectional",
        config_parameter="prospectconnect_sync.sync_direction",
    )

    pc_trigger_mode = fields.Selection(
        [
            ("on_create", "On Create"),
            ("on_update", "On Update"),
            ("on_create_update", "On Create/Update"),
        ],
        string="Odoo → PC Trigger",
        default="on_create_update",
        config_parameter="prospectconnect_sync.trigger_mode",
    )

    # What to sync
    pc_sync_contacts = fields.Boolean(
        string="Contacts",
        config_parameter="prospectconnect_sync.sync_contacts",
        default=True,
    )
    pc_sync_deals = fields.Boolean(
        string="Opportunities",
        config_parameter="prospectconnect_sync.sync_deals",
    )
    pc_sync_tasks = fields.Boolean(
        string="Tasks",
        config_parameter="prospectconnect_sync.sync_tasks",
    )
    pc_sync_notes = fields.Boolean(
        string="Notes",
        config_parameter="prospectconnect_sync.sync_notes",
    )

    # Polling interval (cron)
    pc_poll_interval_minutes = fields.Integer(
        string="Minutes between polls (cron)",
        default=5,
        config_parameter="prospectconnect_sync.poll_interval_minutes",
    )

    # Read-only last sync timestamps (computed from pc.sync.state)
    pc_last_sync_contacts = fields.Datetime(
        string="Contacts Last Sync", readonly=True, compute="_compute_pc_last_sync"
    )
    pc_last_sync_deals = fields.Datetime(
        string="Opportunities Last Sync", readonly=True, compute="_compute_pc_last_sync"
    )
    pc_last_sync_tasks = fields.Datetime(
        string="Tasks Last Sync", readonly=True, compute="_compute_pc_last_sync"
    )
    pc_last_sync_notes = fields.Datetime(
        string="Notes Last Sync", readonly=True, compute="_compute_pc_last_sync"
    )

    def _compute_pc_last_sync(self):
        SyncState = self.env["pc.sync.state"].sudo()
        mapping = {
            "contact": "pc_last_sync_contacts",
            "deal": "pc_last_sync_deals",
            "task": "pc_last_sync_tasks",
            "note": "pc_last_sync_notes",
        }
        for rec in self:
            for obj_type, field_name in mapping.items():
                state = SyncState.search(
                    [("object_type", "=", obj_type)], limit=1
                )
                rec[field_name] = state.last_pull_at if state else False

    # Buttons

    def action_pc_test_connection(self):
        """Test API key & base URL with a very small request."""
        self.ensure_one()
        if not self.pc_api_key or not self.pc_base_url:
            raise UserError(_("Please configure API key and Base URL first."))

        if not requests:
            raise UserError(
                _(
                    "Python 'requests' library is not available on the server. "
                    "Please install it to use ProspectConnect sync."
                )
            )

        url = self.pc_base_url.rstrip("/") + "/contact/upsert"
        headers = {
            "Accept": "application/json",
            "Authorization": self.pc_api_key,
            "Content-Type": "application/json",
        }
        # Use a harmless dummy email to avoid polluting real data.
        payload = {
            "data": {
                "email": "odoo_test_connection@example.com",
                "forceCreate": False,
            }
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            if resp.status_code not in (200, 201):
                raise UserError(
                    _("Connection failed: HTTP %s\nResponse: %s")
                    % (resp.status_code, resp.text[:500])
                )
        except Exception as e:  # pragma: no cover
            _logger.exception("ProspectConnect test connection error")
            raise UserError(_("Connection error: %s") % e)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("ProspectConnect"),
                "message": _("Connection successful."),
                "type": "success",
            },
        }

    def action_pc_sync_now(self):
        """Manually trigger incremental sync (same as cron)."""
        self.ensure_one()
        self.env["pc.sync.state"].sudo().run_incremental_sync()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("ProspectConnect"),
                "message": _("Manual sync started in the background."),
                "type": "info",
            },
        }

    def action_pc_fetch_users(self):
        """Fetch users from ProspectConnect into mapping model."""
        self.ensure_one()
        self.env["pc.user.mapping"].sudo().fetch_from_api()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("ProspectConnect"),
                "message": _("User mapping updated from ProspectConnect."),
                "type": "info",
            },
        }

    def action_pc_fetch_pipelines(self):
        """Fetch pipelines/stages from ProspectConnect into mapping model."""
        self.ensure_one()
        self.env["pc.pipeline.mapping"].sudo().fetch_from_api()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("ProspectConnect"),
                "message": _("Pipeline/Stage mapping updated from ProspectConnect."),
                "type": "info",
            },
        }
