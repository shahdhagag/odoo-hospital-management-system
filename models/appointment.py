from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Appointment(models.Model):
    _name = 'hms.appointment'
    _description = 'Hospital Appointment'
    _rec_name = 'name'
    _order = 'appointment_datetime desc'

    # =========================
    # Basic Information
    # =========================

    name = fields.Char(
        string='Appointment Reference',
        required=True,
        copy=False,
        readonly=True,
        default='New',
    )

    patient_id = fields.Many2one(
        'hms.patient',
        string='Patient',
        required=True,
        ondelete='restrict',
    )

    doctor_id = fields.Many2one(
        'hms.doctors',
        string='Doctor',
        required=True,
        ondelete='restrict',
    )

    department_id = fields.Many2one(
        'hms.department',
        string='Department',
        related='patient_id.department_id',
        store=True,
        readonly=True,
    )

    # =========================
    # Appointment Schedule
    # =========================

    appointment_datetime = fields.Datetime(
        string='Appointment Date & Time',
        required=True,
        default=fields.Datetime.now,
    )

    duration = fields.Integer(
        string='Duration (Minutes)',
        required=True,
        default=30,
    )

    end_datetime = fields.Datetime(
        string='End Date & Time',
        compute='_compute_end_datetime',
        store=True,
    )

    # =========================
    # Medical Information
    # =========================

    reason = fields.Char(
        string='Reason for Visit',
        required=True,
    )

    symptoms = fields.Text(
        string='Symptoms',
    )

    cancellation_reason = fields.Text(
        string='Cancellation Reason',
    )

    # =========================
    # Appointment Workflow
    # =========================

    state = fields.Selection(
        [
            ('scheduled', 'Scheduled'),
            ('confirmed', 'Confirmed'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
            ('no_show', 'No Show'),
        ],
        string='Status',
        required=True,
        default='scheduled',
        copy=False,
    )

    # =========================
    # Computed Fields
    # =========================

    @api.depends('appointment_datetime', 'duration')
    def _compute_end_datetime(self):
        for appointment in self:
            if appointment.appointment_datetime and appointment.duration > 0:
                start = fields.Datetime.to_datetime(
                    appointment.appointment_datetime
                )

                end = start + timedelta(
                    minutes=appointment.duration
                )

                appointment.end_datetime = fields.Datetime.to_string(end)
            else:
                appointment.end_datetime = False

    # =========================
    # Validations
    # =========================

    @api.constrains('duration')
    def _check_duration(self):
        for appointment in self:
            if appointment.duration <= 0:
                raise ValidationError(
                    _('Appointment duration must be greater than zero.')
                )

    @api.constrains('appointment_datetime', 'duration', 'doctor_id', 'state')
    def _check_appointment_datetime(self):
        for appointment in self:
            if not appointment.appointment_datetime:
                continue

            start = fields.Datetime.to_datetime(
                appointment.appointment_datetime
            )

            end = start + timedelta(
                minutes=appointment.duration
            )

            overlapping_appointments = self.sudo().search([
                ('id', '!=', appointment.id),
                ('doctor_id', '=', appointment.doctor_id.id),
                ('state', 'not in', ['cancelled', 'no_show']),
                ('appointment_datetime', '<', fields.Datetime.to_string(end)),
                ('end_datetime', '>', fields.Datetime.to_string(start)),
            ], limit=1)

            if overlapping_appointments:
                raise ValidationError(
                    _(
                        'This doctor already has an appointment '
                        'during the selected time.'
                    )
                )

    @api.constrains('state', 'cancellation_reason')
    def _check_cancellation_reason(self):
        for appointment in self:
            if (
                appointment.state == 'cancelled'
                and not (appointment.cancellation_reason or '').strip()
            ):
                raise ValidationError(
                    _('Please provide a reason for cancelling the appointment.')
                )

    # =========================
    # Create Appointment
    # =========================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code(
                        'hms.appointment'
                    ) or 'New'
                )

        return super().create(vals_list)

    # =========================
    # Workflow Actions
    # =========================

    def action_confirm(self):
        for appointment in self:
            if appointment.state != 'scheduled':
                raise ValidationError(
                    _('Only scheduled appointments can be confirmed.')
                )

            appointment.state = 'confirmed'

    def action_start(self):
        for appointment in self:
            if appointment.state != 'confirmed':
                raise ValidationError(
                    _('Only confirmed appointments can be started.')
                )

            if fields.Datetime.to_datetime(
                appointment.appointment_datetime
            ) > fields.Datetime.to_datetime(fields.Datetime.now()):
                raise ValidationError(
                    _('You cannot start an appointment before its scheduled time.')
                )

            appointment.state = 'in_progress'

    def action_complete(self):
        for appointment in self:
            if appointment.state != 'in_progress':
                raise ValidationError(
                    _('Only appointments in progress can be completed.')
                )

            appointment.state = 'completed'

    def action_cancel(self):
        for appointment in self:
            if appointment.state in ['completed', 'cancelled', 'no_show']:
                raise ValidationError(
                    _('This appointment cannot be cancelled.')
                )

            if not (appointment.cancellation_reason or '').strip():
                raise ValidationError(
                    _('Enter a cancellation reason before cancelling.')
                )

            appointment.state = 'cancelled'

    def action_mark_no_show(self):
        for appointment in self:
            if appointment.state not in ['scheduled', 'confirmed']:
                raise ValidationError(
                    _(
                        'Only scheduled or confirmed appointments '
                        'can be marked as no-show.'
                    )
                )

            appointment.state = 'no_show'