# prospectconnect_sync/models/mail_activity.py
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MailActivity(models.Model):
    _inherit = "mail.activity"

    pc_task_id = fields.Char(string="ProspectConnect Task ID", index=True)
    pc_last_sync_at = fields.Datetime(string="PC Task Last Sync At")
    pc_last_remote_update = fields.Datetime(
        string="PC Task Last Remote Update",
        help="Timestamp of last update from ProspectConnect (for conflict resolution)"
    )
    pc_remote_assignee_id = fields.Char(
        string="PC Assignee ID",
        help="ProspectConnect user ID of the assignee"
    )

    @api.model_create_multi
    def create(self, vals_list):
        activities = super().create(vals_list)
        activities._pc_maybe_sync_to_pc(trigger="on_create")
        return activities

    def write(self, vals):
        res = super().write(vals)
        self._pc_maybe_sync_to_pc(trigger="on_update")
        return res

    def _pc_maybe_sync_to_pc(self, trigger):
        """Schedule sync jobs for tasks/activities."""
        config = self.env["ir.config_parameter"].sudo()
        if not config.get_param("prospectconnect_sync.sync_tasks", "False") == "True":
            return

        trigger_mode = config.get_param(
            "prospectconnect_sync.trigger_mode", "on_create_update"
        )
        if trigger_mode == "on_create" and trigger != "on_create":
            return
        if trigger_mode == "on_update" and trigger != "on_update":
            return

        direction = config.get_param(
            "prospectconnect_sync.sync_direction", "bidirectional"
        )
        if direction not in ("odoo_to_pc", "bidirectional"):
            return

        for activity in self:
            self.env["pc.sync.job"].sudo().create(
                {
                    "direction": "odoo_to_pc",
                    "object_type": "task",
                    "odoo_model": activity._name,
                    "odoo_res_id": activity.id,
                }
            )
            _logger.debug(
                "ProspectConnect: queued sync job for task %s (%s)",
                activity.id,
                activity.summary,
            )
