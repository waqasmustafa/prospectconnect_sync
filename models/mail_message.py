# prospectconnect_sync/models/mail_message.py
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MailMessage(models.Model):
    _inherit = "mail.message"

    pc_note_id = fields.Char(string="ProspectConnect Note ID", index=True)
    pc_last_sync_at = fields.Datetime(string="PC Note Last Sync At")
    pc_last_remote_update = fields.Datetime(
        string="PC Note Last Remote Update",
        help="Timestamp of last update from ProspectConnect (for conflict resolution)"
    )
    pc_sync_enabled = fields.Boolean(
        string="Sync to ProspectConnect",
        default=False,
        help="Enable syncing this note to ProspectConnect"
    )

    @api.model_create_multi
    def create(self, vals_list):
        messages = super().create(vals_list)
        # Only sync notes (internal messages) on contacts and opportunities
        messages_to_sync = messages.filtered(
            lambda m: m.message_type == 'comment' 
            and m.model in ('res.partner', 'crm.lead')
            and not m.pc_note_id  # Don't sync messages coming from PC
        )
        if messages_to_sync:
            for msg in messages_to_sync:
                msg.pc_sync_enabled = True
            messages_to_sync._pc_maybe_sync_to_pc(trigger="on_create")
        return messages

    def write(self, vals):
        res = super().write(vals)
        # Only sync if content changed
        if 'body' in vals:
            self.filtered(lambda m: m.pc_sync_enabled)._pc_maybe_sync_to_pc(trigger="on_update")
        return res

    def _pc_maybe_sync_to_pc(self, trigger):
        """Schedule sync jobs for notes."""
        config = self.env["ir.config_parameter"].sudo()
        if not config.get_param("prospectconnect_sync.sync_notes", "False") == "True":
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

        for message in self:
            self.env["pc.sync.job"].sudo().create(
                {
                    "direction": "odoo_to_pc",
                    "object_type": "note",
                    "odoo_model": message._name,
                    "odoo_res_id": message.id,
                }
            )
            _logger.debug(
                "ProspectConnect: queued sync job for note %s on %s",
                message.id,
                message.model,
            )
