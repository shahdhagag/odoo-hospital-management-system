from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class Prescription(models.Model):
    _name = 'hms.prescription'
    _description = 'Medical Prescription'
    _rec_name = 'name'
    _order = 'prescription_date desc'

    name = fields.Char(
        string='Prescription Reference',
        required=True,
        readonly=True,
        copy=False,
        default='New',
        index=True,
    )

    encounter_id = fields.Many2one(
        'hms.medical.encounter',
        string='Medical Encounter',
        required=True,
        ondelete='restrict',
        index=True,
    )

    patient_id = fields.Many2one(
        'hms.patient',
        string='Patient',
        related='encounter_id.patient_id',
        store=True,
        readonly=True,
    )

    doctor_id = fields.Many2one(
        'hms.doctors',
        string='Doctor',
        related='encounter_id.doctor_id',
        store=True,
        readonly=True,
    )

    prescription_date = fields.Datetime(
        string='Prescription Date',
        required=True,
        default=fields.Datetime.now,
    )

    line_ids = fields.One2many(
        'hms.prescription.line',
        'prescription_id',
        string='Medications',
        copy=True,
    )

    notes = fields.Text(string='Notes')

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        required=True,
        default='draft',
        copy=False,
        index=True,
    )

    # =========================
    # Create Prescription
    # =========================

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [vals.copy() for vals in vals_list]

        for vals in vals_list:
            encounter = self.env['hms.medical.encounter'].browse(
                vals.get('encounter_id')
            ).exists()

            if not encounter:
                raise ValidationError(
                    _('A valid medical encounter is required.')
                )

            if encounter.state != 'in_progress':
                raise ValidationError(
                    _(
                        'A prescription can only be created while '
                        'the encounter is in progress.'
                    )
                )

            # Generate the prescription reference automatically.
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code(
                        'hms.prescription'
                    ) or 'New'
                )

            # Every new prescription must start as a draft.
            vals['state'] = 'draft'

        return super().create(vals_list)

    # =========================
    # Encounter Validation
    # =========================

    @api.constrains('encounter_id')
    def _check_encounter(self):
        for prescription in self:
            if prescription.encounter_id.state != 'in_progress':
                raise ValidationError(
                    _(
                        'A prescription must be linked to an encounter '
                        'that is in progress.'
                    )
                )

    # =========================
    # Protect Prescription
    # =========================

    def write(self, vals):
        allow_state_change = self.env.context.get(
            'allow_prescription_state_change'
        )

        # Prevent changing the state directly outside the workflow actions.
        if 'state' in vals and not allow_state_change:
            raise ValidationError(
                _('Use the prescription workflow actions to change its status.')
            )

        for prescription in self:
            if prescription.state != 'draft':
                # The only permitted write on a confirmed prescription
                # is cancellation through the workflow action.
                allowed_cancel = (
                    allow_state_change
                    and prescription.state == 'confirmed'
                    and vals == {'state': 'cancelled'}
                )

                if not allowed_cancel:
                    raise ValidationError(
                        _(
                            'Only draft prescriptions can be edited. '
                            'Confirmed or cancelled prescriptions are locked.'
                        )
                    )

        return super().write(vals)

    # =========================
    # Confirm Prescription
    # =========================

    def action_confirm(self):
        for prescription in self:
            if prescription.state != 'draft':
                raise ValidationError(
                    _('Only draft prescriptions can be confirmed.')
                )

            if prescription.encounter_id.state != 'in_progress':
                raise ValidationError(
                    _(
                        'The medical encounter must be in progress '
                        'before confirming the prescription.'
                    )
                )

            if not prescription.line_ids:
                raise ValidationError(
                    _('Add at least one medication before confirming.')
                )

        self.with_context(
            allow_prescription_state_change=True
        ).write({
            'state': 'confirmed',
        })

    # =========================
    # Cancel Prescription
    # =========================

    def action_cancel(self):
        for prescription in self:
            if prescription.state == 'cancelled':
                raise ValidationError(
                    _('This prescription is already cancelled.')
                )

        self.with_context(
            allow_prescription_state_change=True
        ).write({
            'state': 'cancelled',
        })
    def unlink(self):
        for prescription in self:
            if prescription.state != 'draft':
                raise ValidationError(
                    _(
                        'Only draft prescriptions can be deleted. '
                        'Confirmed or cancelled prescriptions cannot be deleted.'
                    )
                )

        return super().unlink()

class PrescriptionLine(models.Model):
    _name = 'hms.prescription.line'
    _description = 'Prescription Medication'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)

    prescription_id = fields.Many2one(
        'hms.prescription',
        string='Prescription',
        required=True,
        ondelete='cascade',
        index=True,
    )

    medication_name = fields.Char(
        string='Medication',
        required=True,
    )

    dosage = fields.Char(
        string='Dosage',
        required=True,
        help='For example: 500 mg or 10 ml.',
    )

    frequency = fields.Integer(
        string='Times per Day',
        required=True,
        default=1,
    )

    duration = fields.Integer(
        string='Duration',
        required=True,
        default=1,
    )

    duration_unit = fields.Selection(
        [
            ('day', 'Days'),
            ('week', 'Weeks'),
            ('month', 'Months'),
        ],
        string='Duration Unit',
        required=True,
        default='day',
    )

    instructions = fields.Char(string='Instructions')

    # =========================
    # Create Medication Line
    # =========================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            prescription = self.env['hms.prescription'].browse(
                vals.get('prescription_id')
            ).exists()

            if not prescription:
                raise ValidationError(
                    _('A valid prescription is required.')
                )

            if prescription.state != 'draft':
                raise ValidationError(
                    _(
                        'Medications can only be added to '
                        'a draft prescription.'
                    )
                )

        return super().create(vals_list)

    # =========================
    # Protect Medication Lines
    # =========================

    def write(self, vals):
        for line in self:
            if line.prescription_id.state != 'draft':
                raise ValidationError(
                    _(
                        'Medications can only be changed on '
                        'a draft prescription.'
                    )
                )

        # If moving a line to another prescription, the target
        # prescription must also be in draft.
        if 'prescription_id' in vals:
            target = self.env['hms.prescription'].browse(
                vals['prescription_id']
            ).exists()

            if not target or target.state != 'draft':
                raise ValidationError(
                    _(
                        'A medication can only be assigned to '
                        'a draft prescription.'
                    )
                )

        return super().write(vals)

    def unlink(self):
        for line in self:
            if line.prescription_id.state != 'draft':
                raise ValidationError(
                    _(
                        'Medications cannot be deleted from '
                        'a confirmed or cancelled prescription.'
                    )
                )

        return super().unlink()

    # =========================
    # Medication Validation
    # =========================

    @api.constrains(
        'medication_name',
        'dosage',
        'frequency',
        'duration',
    )
    def _check_values(self):
        for line in self:
            if not (line.medication_name or '').strip():
                raise ValidationError(
                    _('Medication name is required.')
                )

            if not (line.dosage or '').strip():
                raise ValidationError(
                    _('Medication dosage is required.')
                )

            if line.frequency <= 0:
                raise ValidationError(
                    _('Medication frequency must be greater than zero.')
                )

            if line.duration <= 0:
                raise ValidationError(
                    _('Medication duration must be greater than zero.')
                )
