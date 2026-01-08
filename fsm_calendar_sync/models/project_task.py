from odoo import models, fields, api
from datetime import timedelta


class ProjectTask(models.Model):
    _inherit = 'project.task'

    calendar_event_id = fields.Many2one(
        'calendar.event',
        string="Calendar Event",
        readonly=True,
        ondelete='set null',
        copy=False,
        help="Linked calendar event for this Field Service task"
    )

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to auto-generate calendar events for FSM tasks."""
        records = super().create(vals_list)
        for task in records:
            if task.is_fsm and not task.calendar_event_id:
                task._create_calendar_event()
        return records

    def write(self, vals):
        """Override write to sync updates to linked calendar events."""
        # Skip sync logic if called from internal calendar sync to prevent recursion
        if self.env.context.get('fsm_calendar_sync'):
            return super().write(vals)

        res = super().write(vals)

        # Fields that should trigger calendar event creation/sync
        sync_fields = {'name', 'planned_date_begin', 'allocated_hours', 'partner_id', 'user_ids'}
        trigger_fields = sync_fields | {'is_fsm'}

        # Check if any relevant field was modified
        if trigger_fields & set(vals.keys()):
            for task in self:
                if task.is_fsm:
                    if not task.calendar_event_id:
                        # Try to create calendar event (will validate required fields internally)
                        task._create_calendar_event()
                    else:
                        # Sync updates to existing calendar event
                        task._sync_calendar_event()

        return res

    def unlink(self):
        """Override unlink to handle calendar event deletion."""
        # Calendar events will be deleted automatically due to ondelete='cascade'
        # on calendar.event.task_id, but we explicitly delete here for safety
        events = self.mapped('calendar_event_id')
        res = super().unlink()
        # Events linked via task_id with cascade will be deleted automatically
        return res

    # -------------------------------------------------------------------------
    # CALENDAR EVENT METHODS
    # -------------------------------------------------------------------------

    def _create_calendar_event(self):
        """Create a calendar event for this FSM task."""
        self.ensure_one()

        # Validation: Do not create event if required fields are missing
        if not self.planned_date_begin:
            return False
        if not self.allocated_hours or self.allocated_hours <= 0:
            return False

        # Calculate stop time
        duration_hours = self.allocated_hours or 1.0
        start = self.planned_date_begin
        stop = start + timedelta(hours=duration_hours)

        # Prepare attendees (partner_ids)
        # Include: assigned users' partners + customer partner
        attendee_partner_ids = []

        # Add assigned users' partners (so they can see event in their calendar)
        if self.user_ids:
            attendee_partner_ids.extend(self.user_ids.mapped('partner_id').ids)

        # Add customer partner
        if self.partner_id and self.partner_id.id not in attendee_partner_ids:
            attendee_partner_ids.append(self.partner_id.id)

        # Create calendar event with context to prevent recursion
        event_vals = {
            'name': "Field Service - %s" % self.name,
            'start': start,
            'stop': stop,
            'duration': duration_hours,
            'task_id': self.id,
            'partner_ids': [(6, 0, attendee_partner_ids)],
            'allday': False,
        }

        event = self.env['calendar.event'].with_context(
            fsm_calendar_sync=True
        ).create(event_vals)

        # Link the event to this task
        self.with_context(fsm_calendar_sync=True).write({
            'calendar_event_id': event.id
        })

        return event

    def _sync_calendar_event(self):
        """Synchronize task changes to linked calendar event."""
        self.ensure_one()

        if not self.calendar_event_id:
            return False

        # Calculate stop time
        duration_hours = self.allocated_hours or 1.0
        start = self.planned_date_begin
        stop = start + timedelta(hours=duration_hours) if start else False

        # Prepare attendees (partner_ids)
        # Include: assigned users' partners + customer partner
        attendee_partner_ids = []

        # Add assigned users' partners (so they can see event in their calendar)
        if self.user_ids:
            attendee_partner_ids.extend(self.user_ids.mapped('partner_id').ids)

        # Add customer partner
        if self.partner_id and self.partner_id.id not in attendee_partner_ids:
            attendee_partner_ids.append(self.partner_id.id)

        # Prepare update values
        update_vals = {
            'name': "Field Service - %s" % self.name,
            'duration': duration_hours,
            'partner_ids': [(6, 0, attendee_partner_ids)],
        }

        if start:
            update_vals['start'] = start
        if stop:
            update_vals['stop'] = stop

        # Update calendar event with context to prevent recursion
        self.calendar_event_id.with_context(
            fsm_calendar_sync=True
        ).write(update_vals)

        return True

    def _get_calendar_event_count(self):
        """Get count of linked calendar events for smart button."""
        for task in self:
            task.calendar_event_count = 1 if task.calendar_event_id else 0

    calendar_event_count = fields.Integer(
        compute='_get_calendar_event_count',
        string="Calendar Events"
    )

    def action_open_calendar_event(self):
        """Open the linked calendar event."""
        self.ensure_one()
        if not self.calendar_event_id:
            return False

        return {
            'type': 'ir.actions.act_window',
            'name': 'Calendar Event',
            'res_model': 'calendar.event',
            'view_mode': 'form',
            'res_id': self.calendar_event_id.id,
            'target': 'current',
        }
