# prospectconnect_sync/models/pc_sync_job.py
import logging
from datetime import datetime

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


class PcSyncJob(models.Model):
    _name = "pc.sync.job"
    _description = "ProspectConnect Sync Job"
    _order = "create_date asc"

    direction = fields.Selection(
        [("odoo_to_pc", "Odoo → ProspectConnect"), ("pc_to_odoo", "ProspectConnect → Odoo")],
        required=True,
    )
    object_type = fields.Selection(
        [
            ("contact", "Contact"),
            ("deal", "Deal"),
            ("task", "Task"),
            ("note", "Note"),
        ],
        required=True,
    )
    odoo_model = fields.Char(string="Odoo Model")
    odoo_res_id = fields.Integer(string="Odoo Record ID")
    pc_id = fields.Char(string="ProspectConnect ID")

    status = fields.Selection(
        [
            ("pending", "Pending"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("failed", "Failed"),
        ],
        default="pending",
        index=True,
    )
    retry_count = fields.Integer(default=0)
    next_retry_at = fields.Datetime()
    error_message = fields.Text()

    # ------------------ CRON PROCESSOR ------------------

    @api.model
    def process_pending_jobs(self, limit=100):
        """Process queued jobs (called from cron & incremental sync)."""
        domain = [("status", "in", ["pending", "failed"])]
        jobs = self.search(domain, limit=limit)
        if not jobs:
            return

        for job in jobs:
            try:
                job.status = "in_progress"
                job._run_single_job()
                job.status = "done"
                job.error_message = False
            except Exception as e:  # pragma: no cover
                _logger.exception("ProspectConnect sync job failed")
                job.status = "failed"
                job.retry_count += 1
                job.error_message = str(e)

    # ------------------ JOB EXECUTION ------------------

    def _run_single_job(self):
        """Execute a single job."""
        self.ensure_one()
        if self.direction == "odoo_to_pc":
            if self.object_type == "contact":
                self._sync_contact_to_pc()
            elif self.object_type == "deal":
                self._sync_deal_to_pc()
            elif self.object_type == "task":
                self._sync_task_to_pc()
            elif self.object_type == "note":
                self._sync_note_to_pc()

    # -------------- HELPER: AUTH + BASE URL ----------------

    @api.model
    def _get_api_context(self):
        icp = self.env["ir.config_parameter"].sudo()
        api_key = icp.get_param("prospectconnect_sync.api_key")
        base_url = icp.get_param(
            "prospectconnect_sync.base_url", "https://api.prospectconnect.ai"
        )
        if not api_key or not base_url:
            raise ValueError("ProspectConnect API key or base URL not configured.")
        if not requests:
            raise ValueError("Python 'requests' library is not available.")
        headers = {
            "Accept": "application/json",
            "Authorization": api_key,
            "Content-Type": "application/json",
        }
        return base_url.rstrip("/"), headers

    def _get_assignee_id(self, odoo_user):
        """Map Odoo user to ProspectConnect user ID."""
        if not odoo_user:
            return None
        mapping = self.env["pc.user.mapping"].search(
            [("odoo_user_id", "=", odoo_user.id)], limit=1
        )
        return mapping.pc_user_id if mapping else None

    def _get_stage_mapping(self, odoo_stage):
        """Map Odoo stage to ProspectConnect stage/pipeline IDs."""
        if not odoo_stage:
            return None, None
        mapping = self.env["pc.pipeline.mapping"].search(
            [("odoo_stage_id", "=", odoo_stage.id)], limit=1
        )
        if mapping:
            return mapping.pc_pipeline_id, mapping.pc_stage_id
        return None, None

    # -------------- CONTACT SYNC ----------------

    def _sync_contact_to_pc(self):
        base_url, headers = self._get_api_context()
        partner = self.env[self.odoo_model].browse(self.odoo_res_id).exists()
        if not partner:
            return

        url = base_url + "/contact/addOrUpdateContact"

        country = partner.country_id
        
        # Get assignee ID
        assignee_id = self._get_assignee_id(partner.pc_assigned_user_id)
        
        payload = {
            "data": {
                "email": partner.email or "",
                "phone": partner.phone or partner.mobile or "",
                "first_name": partner.name.split(" ", 1)[0] if partner.name else "",
                "last_name": partner.name.split(" ", 1)[1] if " " in (partner.name or "") else "",
                "name": partner.name or "",
                "tags": [c.name for c in partner.category_id],
                "address1": partner.street or "",
                "postal_code": partner.zip or "",
                "city": partner.city or "",
                "state": partner.state_id.name if partner.state_id else "",
                "country": {
                    "country_code": country.code if country else "",
                    "name": country.name if country else "",
                },
                "source": partner.pc_lead_source or "",
                "forceCreate": True,
            }
        }
        
        # Add assignee if mapped
        if assignee_id:
            payload["data"]["assignedTo"] = assignee_id

        resp = requests.post(url, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json() if resp.content else {}
        pc_id = data.get("data", {}).get("id") or data.get("id")
        if pc_id:
            partner.write(
                {
                    "pc_contact_id": pc_id,
                    "pc_last_sync_at": fields.Datetime.now(),
                }
            )

    # -------------- DEAL SYNC ----------------

    def _sync_deal_to_pc(self):
        base_url, headers = self._get_api_context()
        lead = self.env[self.odoo_model].browse(self.odoo_res_id).exists()
        if not lead:
            return

        # Get pipeline and stage mapping
        pipeline_id, stage_id = self._get_stage_mapping(lead.stage_id)
        
        # Get assignee ID
        assignee_id = self._get_assignee_id(lead.user_id)
        
        # Get contact ID if linked
        contact_id = None
        if lead.partner_id and lead.partner_id.pc_contact_id:
            contact_id = lead.partner_id.pc_contact_id

        # Determine if update or create
        if lead.pc_deal_id:
            # Update existing deal
            url = base_url + "/deal/updateDeal"
            payload = {
                "dealId": lead.pc_deal_id,
                "name": lead.name or "",
                "value": float(lead.expected_revenue or 0.0),
                "status": "open" if lead.active else "closed",
            }
        else:
            # Create new deal
            url = base_url + "/deal/addDeal"
            payload = {
                "name": lead.name or "",
                "value": float(lead.expected_revenue or 0.0),
                "status": "open",
            }
        
        # Add optional fields
        if pipeline_id:
            payload["pipelineId"] = pipeline_id
        if stage_id:
            payload["stageId"] = stage_id
        if assignee_id:
            payload["assignedTo"] = assignee_id
        if contact_id:
            payload["contactId"] = contact_id
        if lead.description:
            payload["notes"] = lead.description

        resp = requests.post(url, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json() if resp.content else {}
        pc_id = data.get("data", {}).get("id") or data.get("id") or lead.pc_deal_id
        if pc_id:
            lead.write(
                {
                    "pc_deal_id": pc_id,
                    "pc_last_sync_at": fields.Datetime.now(),
                    "pc_remote_pipeline_id": pipeline_id,
                    "pc_remote_stage_id": stage_id,
                }
            )

    # -------------- TASK SYNC ----------------

    def _sync_task_to_pc(self):
        base_url, headers = self._get_api_context()
        activity = self.env[self.odoo_model].browse(self.odoo_res_id).exists()
        if not activity:
            return

        # Get assignee ID
        assignee_id = self._get_assignee_id(activity.user_id)
        
        # Get related contact/deal IDs
        contact_ids = []
        deal_ids = []
        
        if activity.res_model == "res.partner" and activity.res_id:
            partner = self.env["res.partner"].browse(activity.res_id).exists()
            if partner and partner.pc_contact_id:
                contact_ids.append(partner.pc_contact_id)
        elif activity.res_model == "crm.lead" and activity.res_id:
            lead = self.env["crm.lead"].browse(activity.res_id).exists()
            if lead and lead.pc_deal_id:
                deal_ids.append(lead.pc_deal_id)
            if lead and lead.partner_id and lead.partner_id.pc_contact_id:
                contact_ids.append(lead.partner_id.pc_contact_id)

        task_id = activity.pc_task_id

        if task_id:
            # Update existing task
            url = base_url + "/task/updateTask"
            payload = {
                "taskId": task_id,
                "name": activity.summary or "Task",
                "description": activity.note or "",
                "priority": "medium",
                "completed": activity.state == "done",
            }
        else:
            # Create new task
            url = base_url + "/task/createTask"
            payload = {
                "name": activity.summary or "Task",
                "priority": "medium",
                "description": activity.note or "",
                "tags": [],
                "contact_ids": contact_ids,
                "deal_ids": deal_ids,
            }
        
        # Add due date
        if activity.date_deadline:
            payload["due_date"] = activity.date_deadline.isoformat()
            payload["due_time"] = activity.date_deadline.isoformat()
        
        # Add assignee
        if assignee_id:
            payload["assignedTo"] = assignee_id

        resp = requests.post(url, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json() if resp.content else {}
        new_id = data.get("taskId") or data.get("data", {}).get("id") or data.get("id")
        if new_id and not task_id:
            activity.write(
                {
                    "pc_task_id": new_id,
                    "pc_last_sync_at": fields.Datetime.now(),
                }
            )

    # -------------- NOTE SYNC ----------------

    def _sync_note_to_pc(self):
        base_url, headers = self._get_api_context()
        message = self.env[self.odoo_model].browse(self.odoo_res_id).exists()
        if not message or not message.pc_sync_enabled:
            return

        # Get related contact/deal ID
        contact_id = None
        deal_id = None
        
        if message.model == "res.partner" and message.res_id:
            partner = self.env["res.partner"].browse(message.res_id).exists()
            if partner and partner.pc_contact_id:
                contact_id = partner.pc_contact_id
        elif message.model == "crm.lead" and message.res_id:
            lead = self.env["crm.lead"].browse(message.res_id).exists()
            if lead and lead.pc_deal_id:
                deal_id = lead.pc_deal_id

        if not contact_id and not deal_id:
            _logger.warning("Cannot sync note %s: no linked contact or deal", message.id)
            return

        # Create note (assuming notes are always created, not updated)
        url = base_url + "/note/createNote"
        payload = {
            "body": message.body or "",
            "userId": message.author_id.id if message.author_id else None,
        }
        
        if contact_id:
            payload["contactId"] = contact_id
        if deal_id:
            payload["dealId"] = deal_id

        resp = requests.post(url, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json() if resp.content else {}
        pc_id = data.get("data", {}).get("id") or data.get("id")
        if pc_id:
            message.write(
                {
                    "pc_note_id": pc_id,
                    "pc_last_sync_at": fields.Datetime.now(),
                }
            )
