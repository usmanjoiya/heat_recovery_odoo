from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    task_id = fields.Many2one(
        'project.task',
        string="Field Service Task",
        readonly=True,
        ondelete='cascade',
        copy=False,
        help="Linked Field Service task. If set, this event is controlled by the task."
    )

    is_fsm_controlled = fields.Boolean(
        compute='_compute_is_fsm_controlled',
        string="FSM Controlled",
        help="Indicates if this event is controlled by a Field Service task"
    )

    @api.depends('task_id')
    def _compute_is_fsm_controlled(self):
        """Compute if this event is controlled by an FSM task."""
        for event in self:
            event.is_fsm_controlled = bool(event.task_id)

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES - Prevent circular updates
    # -------------------------------------------------------------------------

    def write(self, vals):
        """Override write to prevent manual edits on FSM-controlled events."""
        # Skip validation if called from FSM sync
        if self.env.context.get('fsm_calendar_sync'):
            return super().write(vals)

        # Protected fields that cannot be modified on FSM-controlled events
        protected_fields = {
            'name', 'start', 'stop', 'duration', 'partner_ids', 'task_id', 'allday'
        }

        # Check if any protected field is being modified
        modified_protected = protected_fields & set(vals.keys())

        if modified_protected:
            for event in self:
                if event.task_id:
                    raise UserError(_(
                        "This calendar event is linked to Field Service task '%s'. "
                        "Please modify the task directly to update the calendar event.\n\n"
                        "Protected fields: %s"
                    ) % (event.task_id.name, ', '.join(modified_protected)))

        return super().write(vals)

    def unlink(self):
        """Override unlink to clear task reference when event is deleted."""
        # Clear the calendar_event_id on linked tasks before deletion
        tasks = self.mapped('task_id')
        if tasks:
            tasks.with_context(fsm_calendar_sync=True).write({
                'calendar_event_id': False
            })
        return super().unlink()

    # -------------------------------------------------------------------------
    # ACTION METHODS
    # -------------------------------------------------------------------------

    def action_open_fsm_task(self):
        """Open the linked Field Service task."""
        self.ensure_one()
        if not self.task_id:
            return False

        return {
            'type': 'ir.actions.act_window',
            'name': 'Field Service Task',
            'res_model': 'project.task',
            'view_mode': 'form',
            'res_id': self.task_id.id,
            'target': 'current',
        }
