# prospectconnect_sync/models/pc_sync_state.py
import logging
from datetime import datetime, timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


class PcSyncState(models.Model):
    _name = "pc.sync.state"
    _description = "ProspectConnect Sync State"

    object_type = fields.Selection(
        [
            ("contact", "Contact"),
            ("deal", "Deal"),
            ("task", "Task"),
            ("note", "Note"),
        ],
        required=True,
    )
    last_pull_at = fields.Datetime(string="Last Pull At")
    last_push_at = fields.Datetime(string="Last Push At")

    _sql_constraints = [
        ("pc_state_unique", "unique(object_type)", "Only one state per object type."),
    ]

    # ------------- CRON / SERVER ACTION ENTRYPOINTS -------------

    @api.model
    def run_incremental_sync(self):
        """Called by cron + 'Sync Now' button.
        
        Processes pending push jobs and pulls updates from ProspectConnect.
        """
        _logger.info("ProspectConnect incremental sync started.")
        
        # Process pending push jobs first
        self.env["pc.sync.job"].process_pending_jobs()
        
        # Pull updates from ProspectConnect
        config = self.env["ir.config_parameter"].sudo()
        direction = config.get_param("prospectconnect_sync.sync_direction", "bidirectional")
        
        if direction in ("pc_to_odoo", "bidirectional"):
            if config.get_param("prospectconnect_sync.sync_contacts") == "True":
                self._pull_contacts()
            if config.get_param("prospectconnect_sync.sync_deals") == "True":
                self._pull_deals()
            if config.get_param("prospectconnect_sync.sync_tasks") == "True":
                self._pull_tasks()
            if config.get_param("prospectconnect_sync.sync_notes") == "True":
                self._pull_notes()
        
        _logger.info("ProspectConnect incremental sync finished.")

    @api.model
    def run_nightly_reconciliation(self):
        """Nightly deeper reconciliation job (2 AM)."""
        _logger.info("ProspectConnect nightly reconciliation started.")
        
        # Run a full sync with wider time window
        config = self.env["ir.config_parameter"].sudo()
        
        # Temporarily override last_pull_at to get last 7 days
        for obj_type in ["contact", "deal", "task", "note"]:
            state = self.search([("object_type", "=", obj_type)], limit=1)
            if state:
                # Save current timestamp
                original_timestamp = state.last_pull_at
                # Set to 7 days ago
                state.last_pull_at = datetime.now() - timedelta(days=7)
        
        # Run incremental sync (which will now pull 7 days of data)
        self.run_incremental_sync()
        
        _logger.info("ProspectConnect nightly reconciliation finished.")

    # ------------- HELPER METHODS -------------

    def _get_api_context(self):
        """Get API configuration."""
        icp = self.env["ir.config_parameter"].sudo()
        api_key = icp.get_param("prospectconnect_sync.api_key")
        base_url = icp.get_param(
            "prospectconnect_sync.base_url", "https://api.prospectconnect.ai"
        )
        if not api_key or not base_url:
            _logger.warning("ProspectConnect API not configured, skipping pull")
            return None, None
        if not requests:
            _logger.error("Python 'requests' library is not available")
            return None, None
        headers = {
            "Accept": "application/json",
            "Authorization": api_key,
            "Content-Type": "application/json",
        }
        return base_url.rstrip("/"), headers

    def _find_odoo_user_by_pc_id(self, pc_user_id):
        """Find Odoo user by ProspectConnect user ID."""
        if not pc_user_id:
            return None
        mapping = self.env["pc.user.mapping"].search(
            [("pc_user_id", "=", pc_user_id)], limit=1
        )
        return mapping.odoo_user_id if mapping else None

    def _find_odoo_stage_by_pc_ids(self, pc_pipeline_id, pc_stage_id):
        """Find Odoo stage by ProspectConnect pipeline and stage IDs."""
        if not pc_stage_id:
            return None
        mapping = self.env["pc.pipeline.mapping"].search(
            [("pc_stage_id", "=", pc_stage_id)], limit=1
        )
        return mapping.odoo_stage_id if mapping else None

    # ------------- PULL CONTACTS -------------

    def _pull_contacts(self):
        """Pull updated contacts from ProspectConnect."""
        base_url, headers = self._get_api_context()
        if not base_url:
            return

        state = self.search([("object_type", "=", "contact")], limit=1)
        if not state:
            state = self.create({"object_type": "contact"})

        # Get timestamp for incremental pull
        since = state.last_pull_at or (datetime.now() - timedelta(days=30))
        
        url = base_url + "/contacts/list"
        params = {
            "updatedAfter": since.isoformat(),
            "limit": 100,
        }

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            contacts = data.get("data", []) or data.get("contacts", [])
            
            _logger.info(f"Pulled {len(contacts)} contacts from ProspectConnect")
            
            for contact_data in contacts:
                self._upsert_contact_from_pc(contact_data)
            
            # Update last pull timestamp
            state.last_pull_at = datetime.now()
            
        except Exception as e:
            _logger.exception("Error pulling contacts from ProspectConnect")

    def _upsert_contact_from_pc(self, contact_data):
        """Create or update Odoo contact from ProspectConnect data."""
        pc_id = contact_data.get("id")
        if not pc_id:
            return

        # Find existing contact
        partner = self.env["res.partner"].search(
            [("pc_contact_id", "=", pc_id)], limit=1
        )

        # Prepare values
        vals = {
            "name": contact_data.get("name") or contact_data.get("firstName", "") + " " + contact_data.get("lastName", ""),
            "email": contact_data.get("email"),
            "phone": contact_data.get("phone"),
            "street": contact_data.get("address1"),
            "city": contact_data.get("city"),
            "zip": contact_data.get("postalCode"),
            "pc_contact_id": pc_id,
            "pc_last_remote_update": datetime.now(),
            "pc_lead_source": contact_data.get("source"),
        }

        # Map country
        country_code = contact_data.get("country", {}).get("country_code") if isinstance(contact_data.get("country"), dict) else None
        if country_code:
            country = self.env["res.country"].search([("code", "=", country_code)], limit=1)
            if country:
                vals["country_id"] = country.id

        # Map state
        state_name = contact_data.get("state")
        if state_name and vals.get("country_id"):
            state = self.env["res.country.state"].search([
                ("name", "=ilike", state_name),
                ("country_id", "=", vals["country_id"])
            ], limit=1)
            if state:
                vals["state_id"] = state.id

        # Map assignee
        pc_assignee_id = contact_data.get("assignedTo")
        if pc_assignee_id:
            vals["pc_remote_assignee_id"] = pc_assignee_id
            odoo_user = self._find_odoo_user_by_pc_id(pc_assignee_id)
            if odoo_user:
                vals["pc_assigned_user_id"] = odoo_user.id

        # Map tags
        tags = contact_data.get("tags", [])
        if tags:
            tag_ids = []
            for tag_name in tags:
                tag = self.env["res.partner.category"].search([("name", "=", tag_name)], limit=1)
                if not tag:
                    tag = self.env["res.partner.category"].create({"name": tag_name})
                tag_ids.append(tag.id)
            vals["category_id"] = [(6, 0, tag_ids)]

        if partner:
            # Update existing
            # TODO: Add conflict resolution based on timestamps
            partner.write(vals)
            _logger.debug(f"Updated contact {partner.id} from ProspectConnect")
        else:
            # Create new
            partner = self.env["res.partner"].create(vals)
            _logger.debug(f"Created contact {partner.id} from ProspectConnect")

    # ------------- PULL DEALS -------------

    def _pull_deals(self):
        """Pull updated deals from ProspectConnect."""
        base_url, headers = self._get_api_context()
        if not base_url:
            return

        state = self.search([("object_type", "=", "deal")], limit=1)
        if not state:
            state = self.create({"object_type": "deal"})

        since = state.last_pull_at or (datetime.now() - timedelta(days=30))
        
        url = base_url + "/deals/list"
        params = {
            "updatedAfter": since.isoformat(),
            "limit": 100,
        }

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            deals = data.get("data", []) or data.get("deals", [])
            
            _logger.info(f"Pulled {len(deals)} deals from ProspectConnect")
            
            for deal_data in deals:
                self._upsert_deal_from_pc(deal_data)
            
            state.last_pull_at = datetime.now()
            
        except Exception as e:
            _logger.exception("Error pulling deals from ProspectConnect")

    def _upsert_deal_from_pc(self, deal_data):
        """Create or update Odoo opportunity from ProspectConnect data."""
        pc_id = deal_data.get("id")
        if not pc_id:
            return

        lead = self.env["crm.lead"].search([("pc_deal_id", "=", pc_id)], limit=1)

        vals = {
            "name": deal_data.get("name") or "Deal",
            "type": "opportunity",
            "expected_revenue": float(deal_data.get("value", 0)),
            "pc_deal_id": pc_id,
            "pc_last_remote_update": datetime.now(),
            "active": deal_data.get("status") != "closed",
        }

        # Map contact
        contact_id = deal_data.get("contactId")
        if contact_id:
            partner = self.env["res.partner"].search([("pc_contact_id", "=", contact_id)], limit=1)
            if partner:
                vals["partner_id"] = partner.id

        # Map stage
        pc_pipeline_id = deal_data.get("pipelineId")
        pc_stage_id = deal_data.get("stageId")
        if pc_stage_id:
            vals["pc_remote_pipeline_id"] = pc_pipeline_id
            vals["pc_remote_stage_id"] = pc_stage_id
            odoo_stage = self._find_odoo_stage_by_pc_ids(pc_pipeline_id, pc_stage_id)
            if odoo_stage:
                vals["stage_id"] = odoo_stage.id

        # Map assignee
        pc_assignee_id = deal_data.get("assignedTo")
        if pc_assignee_id:
            vals["pc_remote_assignee_id"] = pc_assignee_id
            odoo_user = self._find_odoo_user_by_pc_id(pc_assignee_id)
            if odoo_user:
                vals["user_id"] = odoo_user.id

        # Map notes
        if deal_data.get("notes"):
            vals["description"] = deal_data.get("notes")

        if lead:
            lead.write(vals)
            _logger.debug(f"Updated opportunity {lead.id} from ProspectConnect")
        else:
            lead = self.env["crm.lead"].create(vals)
            _logger.debug(f"Created opportunity {lead.id} from ProspectConnect")

    # ------------- PULL TASKS -------------

    def _pull_tasks(self):
        """Pull updated tasks from ProspectConnect."""
        base_url, headers = self._get_api_context()
        if not base_url:
            return

        state = self.search([("object_type", "=", "task")], limit=1)
        if not state:
            state = self.create({"object_type": "task"})

        since = state.last_pull_at or (datetime.now() - timedelta(days=30))
        
        url = base_url + "/tasks/list"
        params = {
            "updatedAfter": since.isoformat(),
            "limit": 100,
        }

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            tasks = data.get("data", []) or data.get("tasks", [])
            
            _logger.info(f"Pulled {len(tasks)} tasks from ProspectConnect")
            
            for task_data in tasks:
                self._upsert_task_from_pc(task_data)
            
            state.last_pull_at = datetime.now()
            
        except Exception as e:
            _logger.exception("Error pulling tasks from ProspectConnect")

    def _upsert_task_from_pc(self, task_data):
        """Create or update Odoo activity from ProspectConnect data."""
        pc_id = task_data.get("id") or task_data.get("taskId")
        if not pc_id:
            return

        activity = self.env["mail.activity"].search([("pc_task_id", "=", pc_id)], limit=1)

        vals = {
            "summary": task_data.get("name") or "Task",
            "note": task_data.get("description"),
            "pc_task_id": pc_id,
            "pc_last_remote_update": datetime.now(),
        }

        # Map due date
        due_date = task_data.get("due_date")
        if due_date:
            vals["date_deadline"] = due_date

        # Map completion status
        if task_data.get("completed"):
            vals["state"] = "done"

        # Map assignee
        pc_assignee_id = task_data.get("assignedTo")
        if pc_assignee_id:
            vals["pc_remote_assignee_id"] = pc_assignee_id
            odoo_user = self._find_odoo_user_by_pc_id(pc_assignee_id)
            if odoo_user:
                vals["user_id"] = odoo_user.id

        # Map to contact or deal
        contact_ids = task_data.get("contact_ids", [])
        deal_ids = task_data.get("deal_ids", [])
        
        if contact_ids and contact_ids[0]:
            partner = self.env["res.partner"].search([("pc_contact_id", "=", contact_ids[0])], limit=1)
            if partner:
                vals["res_model"] = "res.partner"
                vals["res_id"] = partner.id
        elif deal_ids and deal_ids[0]:
            lead = self.env["crm.lead"].search([("pc_deal_id", "=", deal_ids[0])], limit=1)
            if lead:
                vals["res_model"] = "crm.lead"
                vals["res_id"] = lead.id

        if activity:
            activity.write(vals)
            _logger.debug(f"Updated activity {activity.id} from ProspectConnect")
        else:
            # Need activity type
            activity_type = self.env["mail.activity.type"].search([], limit=1)
            if activity_type:
                vals["activity_type_id"] = activity_type.id
                activity = self.env["mail.activity"].create(vals)
                _logger.debug(f"Created activity {activity.id} from ProspectConnect")

    # ------------- PULL NOTES -------------

    def _pull_notes(self):
        """Pull updated notes from ProspectConnect."""
        base_url, headers = self._get_api_context()
        if not base_url:
            return

        state = self.search([("object_type", "=", "note")], limit=1)
        if not state:
            state = self.create({"object_type": "note"})

        since = state.last_pull_at or (datetime.now() - timedelta(days=30))
        
        url = base_url + "/notes/list"
        params = {
            "updatedAfter": since.isoformat(),
            "limit": 100,
        }

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            notes = data.get("data", []) or data.get("notes", [])
            
            _logger.info(f"Pulled {len(notes)} notes from ProspectConnect")
            
            for note_data in notes:
                self._upsert_note_from_pc(note_data)
            
            state.last_pull_at = datetime.now()
            
        except Exception as e:
            _logger.exception("Error pulling notes from ProspectConnect")

    def _upsert_note_from_pc(self, note_data):
        """Create Odoo message from ProspectConnect note."""
        pc_id = note_data.get("id")
        if not pc_id:
            return

        # Check if note already exists
        message = self.env["mail.message"].search([("pc_note_id", "=", pc_id)], limit=1)
        if message:
            return  # Don't update existing notes

        # Find the related record
        contact_id = note_data.get("contactId")
        deal_id = note_data.get("dealId")
        
        res_model = None
        res_id = None
        
        if contact_id:
            partner = self.env["res.partner"].search([("pc_contact_id", "=", contact_id)], limit=1)
            if partner:
                res_model = "res.partner"
                res_id = partner.id
        elif deal_id:
            lead = self.env["crm.lead"].search([("pc_deal_id", "=", deal_id)], limit=1)
            if lead:
                res_model = "crm.lead"
                res_id = lead.id

        if not res_model or not res_id:
            _logger.warning(f"Cannot import note {pc_id}: no linked contact or deal found")
            return

        vals = {
            "body": note_data.get("body") or "",
            "message_type": "comment",
            "model": res_model,
            "res_id": res_id,
            "pc_note_id": pc_id,
            "pc_last_remote_update": datetime.now(),
            "pc_sync_enabled": False,  # Don't sync back
        }

        message = self.env["mail.message"].create(vals)
        _logger.debug(f"Created note {message.id} from ProspectConnect")
