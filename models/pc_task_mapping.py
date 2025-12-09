# prospectconnect_sync/models/pc_task_mapping.py
from odoo import fields, models


class PcTaskTypeMapping(models.Model):
    _name = "pc.task.type.mapping"
    _description = "ProspectConnect Task Type Mapping"
    _rec_name = "odoo_activity_type_id"

    odoo_activity_type_id = fields.Many2one(
        "mail.activity.type",
        string="Odoo Activity Type",
        required=True,
        ondelete="cascade",
    )
    pc_task_type_id = fields.Char(string="ProspectConnect Task Type ID", required=True)
    pc_task_type_name = fields.Char(string="ProspectConnect Task Type Name")


class PcTaskStatusMapping(models.Model):
    _name = "pc.task.status.mapping"
    _description = "ProspectConnect Task Status Mapping"
    _rec_name = "pc_task_status_name"

    # Very simple mapping – adapt if you want more complex status logic
    odoo_state = fields.Selection(
        [
            ("planned", "Planned"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Odoo Status",
        required=True,
    )
    pc_task_status_id = fields.Char(
        string="ProspectConnect Task Status ID", required=True
    )
    pc_task_status_name = fields.Char(string="ProspectConnect Task Status Name")
