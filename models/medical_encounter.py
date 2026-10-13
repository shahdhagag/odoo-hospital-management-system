from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MedicalEncounter(models.Model):
    _name = 'hms.medical.encounter'
    _description = 'Medical Encounter'
    _rec_name = 'name'
    _order = 'encounter_date desc'

    # =========================
    # Basic Information
    # =========================

    name = fields.Char(
        string='Encounter Reference',
        required=True,
        readonly=True,
        copy=False,
        default='New',
        index=True,
    )

    appointment_id = fields.Many2one(
        'hms.appointment',
        string='Appointment',
        required=True,
        copy=False,
        ondelete='restrict',
        index=True,
    )

    patient_id = fields.Many2one(
        'hms.patient',
        string='Patient',
        related='appointment_id.patient_id',
        store=True,
        readonly=True,
    )

    doctor_id = fields.Many2one(
        'hms.doctors',
        string='Doctor',
        related='appointment_id.doctor_id',
        store=True,
        readonly=True,
    )

    encounter_date = fields.Datetime(
        string='Encounter Date',
        required=True,
        default=fields.Datetime.now,
    )

    # =========================
    # Medical Information
    # =========================

    chief_complaint = fields.Text(
        string='Chief Complaint',
        required=True,
    )

    symptoms = fields.Text(
        string='Symptoms',
    )

    examination_notes = fields.Html(
        string='Examination Notes',
    )

    diagnosis = fields.Text(
        string='Diagnosis',
    )

    treatment_plan = fields.Html(
        string='Treatment Plan',
    )

    prescription_ids = fields.One2many(
        'hms.prescription',
        'encounter_id',
        string='Prescriptions',
    )

    # =========================
    # Workflow
    # =========================

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        required=True,
        default='draft',
        copy=False,
        index=True,
    )

    # =========================
    # Database Constraints
    # =========================

    _sql_constraints = [
        (
            'unique_encounter_appointment',
            'UNIQUE(appointment_id)',
            'An appointment can have only one medical encounter.',
        ),
    ]

    # =========================
    # Create Encounter
    # =========================

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [vals.copy() for vals in vals_list]

        for vals in vals_list:
            appointment_id = vals.get('appointment_id')

            if not appointment_id:
                raise ValidationError(
                    _('An appointment is required to create an encounter.')
                )

            appointment = self.env['hms.appointment'].browse(
                appointment_id
            ).exists()

            if not appointment:
                raise ValidationError(
                    _('The selected appointment does not exist.')
                )

            if appointment.state != 'in_progress':
                raise ValidationError(
                    _(
                        'You can create a medical encounter only '
                        'when the appointment is in progress.'
                    )
                )

            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code(
                        'hms.medical.encounter'
                    ) or 'New'
                )

        return super().create(vals_list)

    # =========================
    # Workflow Actions
    # =========================

    def action_start(self):
        for encounter in self:
            if encounter.state != 'draft':
                raise ValidationError(
                    _('Only draft encounters can be started.')
                )

            if encounter.appointment_id.state != 'in_progress':
                raise ValidationError(
                    _(
                        'The appointment must be in progress '
                        'before starting the encounter.'
                    )
                )

            encounter.state = 'in_progress'

    def action_complete(self):
        for encounter in self:
            if encounter.state != 'in_progress':
                raise ValidationError(
                    _('Only encounters in progress can be completed.')
                )

            if encounter.appointment_id.state != 'in_progress':
                raise ValidationError(
                    _(
                        'The linked appointment must be in progress '
                        'before completing the encounter.'
                    )
                )

            if not (encounter.diagnosis or '').strip():
                raise ValidationError(
                    _('Please enter the diagnosis before completing.')
                )

            if not (encounter.treatment_plan or '').strip():
                raise ValidationError(
                    _('Please enter the treatment plan before completing.')
                )

            encounter.appointment_id.action_complete()
            encounter.state = 'completed'

    def action_cancel(self):
        for encounter in self:
            if encounter.state in ['completed', 'cancelled']:
                raise ValidationError(
                    _('Completed or cancelled encounters cannot be cancelled.')
                )

            encounter.state = 'cancelled'
