import re

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class Patient(models.Model):
    _name = 'hms.patient'
    _description = 'Hospital Patient'
    _rec_name = 'name'
    _order = 'medical_record_number desc, id desc'

    # ==========================================
    # Patient Status Workflow
    # ==========================================
    state = fields.Selection(
        [
            ('new', 'New'),
            ('registered', 'Registered'),
            ('under_examination', 'Under Examination'),
            ('admitted', 'Admitted'),
            ('discharged', 'Discharged'),
            ('archived', 'Archived'),
        ],
        string='Status',
        default='new',
        required=True,
        copy=False,
        index=True,
    )

    # ==========================================
    # Basic Patient Information
    # ==========================================
    medical_record_number = fields.Char(
        string='Medical Record Number',
        readonly=True,
        copy=False,
        index=True,
        default='New',
        required=True,
    )

    first_name = fields.Char(
        string='First Name',
        required=True,
        index=True,
    )

    last_name = fields.Char(
        string='Last Name',
        required=True,
        index=True,
    )

    name = fields.Char(
        string='Patient Name',
        compute='_compute_name',
        store=True,
        index=True,
    )

    @api.depends('first_name', 'last_name')
    def _compute_name(self):
        for record in self:
            first_name = (record.first_name or '').strip()
            last_name = (record.last_name or '').strip()

            record.name = ' '.join(
                part
                for part in (first_name, last_name)
                if part
            )

    birth_date = fields.Date(
        string='Birth Date',
        index=True,
    )

    age = fields.Integer(
        string='Age',
        compute='_compute_age',
    )

    email = fields.Char(
        string='Email',
        index=True,
    )

    address = fields.Text(
        string='Address',
    )

    image = fields.Binary(
        string='Image',
        attachment=True,
    )

    # ==========================================
    # Medical Information
    # ==========================================
    history = fields.Html(
        string='Medical History',
    )

    cr_ratio = fields.Float(
        string='CR Ratio',
        digits=(16, 2),
    )

    blood_type = fields.Selection(
        [
            ('a_positive', 'A+'),
            ('a_negative', 'A-'),
            ('b_positive', 'B+'),
            ('b_negative', 'B-'),
            ('ab_positive', 'AB+'),
            ('ab_negative', 'AB-'),
            ('o_positive', 'O+'),
            ('o_negative', 'O-'),
        ],
        string='Blood Type',
    )

    pcr = fields.Boolean(
        string='PCR Positive',
        default=False,
    )

    # ==========================================
    # Age Calculation
    # ==========================================
    @api.depends('birth_date')
    def _compute_age(self):
        today = fields.Date.today()

        for record in self:
            if not record.birth_date:
                record.age = 0
                continue

            age = today.year - record.birth_date.year

            if (today.month, today.day) < (
                record.birth_date.month,
                record.birth_date.day,
            ):
                age -= 1

            record.age = age

    # ==========================================
    # Department and Doctors
    # ==========================================
    department_id = fields.Many2one(
        'hms.department',
        string='Department',
        ondelete='restrict',
        index=True,
    )

    doctor_ids = fields.Many2many(
        'hms.doctors',
        string='Doctors',
    )

    # ==========================================
    # Responsible User
    # ==========================================
    user_id = fields.Many2one(
        'res.users',
        string='Responsible User',
        required=True,
        default=lambda self: self.env.user,
        index=True,
        ondelete='restrict',
    )

    # ==========================================
    # Database Constraints
    # ==========================================
    _sql_constraints = [
        (
            'unique_patient_email',
            'UNIQUE(email)',
            'Patient email must be unique!',
        ),
        (
            'unique_patient_medical_record_number',
            'UNIQUE(medical_record_number)',
            'Medical record number must be unique!',
        ),
    ]

    # ==========================================
    # Create Patient
    # ==========================================
    @api.model_create_multi
    def create(self, vals_list):
        # Avoid modifying dictionaries supplied by the caller.
        vals_list = [
            vals.copy()
            for vals in vals_list
        ]

        is_manager = self.env.user.has_group(
            'hms.group_hms_manager'
        )

        for vals in vals_list:

            # Normalize patient names.
            for field_name in ('first_name', 'last_name'):
                if vals.get(field_name):
                    vals[field_name] = vals[field_name].strip()

            # Normalize email and convert empty values to False.
            if 'email' in vals:
                email = (vals.get('email') or '').strip().lower()
                vals['email'] = email or False

            # Regular users can only assign patients to themselves.
            if not is_manager:
                if (
                    'user_id' in vals
                    and vals['user_id'] != self.env.uid
                ):
                    raise ValidationError(
                        'You can only assign patients to yourself.'
                    )

                vals['user_id'] = self.env.uid

            # Every new patient must start in the New state.
            if vals.get('state', 'new') != 'new':
                raise ValidationError(
                    'New patients must start in the New state.'
                )

            # Medical record numbers are always generated automatically.
            supplied_number = vals.get('medical_record_number')

            if supplied_number not in (
                False,
                None,
                '',
                'New',
            ):
                raise ValidationError(
                    'Medical record numbers are generated automatically '
                    'and cannot be supplied manually.'
                )

            medical_record_number = (
                self.env['ir.sequence'].next_by_code(
                    'hms.patient'
                )
            )

            if not medical_record_number:
                raise ValidationError(
                    'The patient sequence is not configured. '
                    'Please contact the system administrator.'
                )

            vals['medical_record_number'] = medical_record_number

        return super().create(vals_list)

    # ==========================================
    # Patient Status Actions
    # ==========================================
    def action_register(self):
        for record in self:
            if record.state != 'new':
                raise ValidationError(
                    'Only new patients can be registered.'
                )

            record.write({
                'state': 'registered',
            })

    def action_start_examination(self):
        for record in self:
            if record.state != 'registered':
                raise ValidationError(
                    'Only registered patients can start examination.'
                )

            record.write({
                'state': 'under_examination',
            })

    def action_admit(self):
        for record in self:
            if record.state != 'under_examination':
                raise ValidationError(
                    'Only patients under examination can be admitted.'
                )

            record.write({
                'state': 'admitted',
            })

    def action_discharge(self):
        for record in self:
            if record.state != 'admitted':
                raise ValidationError(
                    'Only admitted patients can be discharged.'
                )

            record.write({
                'state': 'discharged',
            })

    def action_archive(self):
        for record in self:
            if record.state != 'discharged':
                raise ValidationError(
                    'Only discharged patients can be archived.'
                )

            record.write({
                'state': 'archived',
            })

    # ==========================================
    # Validate State Transitions
    # ==========================================
    def _check_state_transition(self, vals):
        if 'state' not in vals:
            return

        allowed_transitions = {
            'new': 'registered',
            'registered': 'under_examination',
            'under_examination': 'admitted',
            'admitted': 'discharged',
            'discharged': 'archived',
        }

        new_state = vals['state']

        for record in self:
            # Allow updating other fields without changing the state.
            if new_state == record.state:
                continue

            expected_state = allowed_transitions.get(
                record.state
            )

            if expected_state != new_state:
                raise ValidationError(
                    'Invalid status transition from %s to %s.'
                    % (
                        record.state,
                        new_state,
                    )
                )

    # ==========================================
    # Validate Department Capacity
    # ==========================================
    def _check_department_capacity(self, vals):
        check_capacity = (
            vals.get('state') == 'admitted'
            or (
                'department_id' in vals
                and any(
                    record.state == 'admitted'
                    for record in self
                )
            )
        )

        if not check_capacity:
            return

        # Determine the resulting department for each affected patient.
        resulting_departments = {}

        for record in self:
            resulting_state = vals.get(
                'state',
                record.state,
            )

            resulting_department_id = vals.get(
                'department_id',
                record.department_id.id,
            )

            if resulting_state != 'admitted':
                continue

            if not resulting_department_id:
                raise ValidationError(
                    'Please assign a department before admitting '
                    'the patient.'
                )

            resulting_departments[record.id] = (
                resulting_department_id
            )

        department_ids = set(
            resulting_departments.values()
        )

        # Use sudo for accurate hospital-wide occupancy counts.
        # This prevents record rules from hiding other patients.
        PatientModel = self.env['hms.patient'].sudo()

        for department_id in department_ids:
            department = self.env['hms.department'].browse(
                department_id
            ).exists()

            if not department:
                raise ValidationError(
                    'The selected department does not exist.'
                )

            if not department.is_opened:
                raise ValidationError(
                    'You cannot admit a patient to a closed department.'
                )

            # Current number of admitted patients in this department.
            current_count = PatientModel.search_count([
                ('department_id', '=', department.id),
                ('state', '=', 'admitted'),
            ])

            # Remove affected patients already counted in this department.
            old_count = sum(
                1
                for record in self
                if record.state == 'admitted'
                and record.department_id.id == department.id
            )

            # Add affected patients according to their resulting assignment.
            new_count = sum(
                1
                for resulting_department_id
                in resulting_departments.values()
                if resulting_department_id == department.id
            )

            projected_count = (
                current_count - old_count + new_count
            )

            if projected_count > department.capacity:
                raise ValidationError(
                    'Department %s has reached its maximum capacity '
                    'of %s admitted patients.'
                    % (
                        department.name,
                        department.capacity,
                    )
                )

    # ==========================================
    # Update Patient
    # ==========================================
    def write(self, vals):
        # Work on a copy to avoid modifying the caller's dictionary.
        vals = vals.copy()

        is_manager = self.env.user.has_group(
            'hms.group_hms_manager'
        )

        # Normalize names.
        for field_name in ('first_name', 'last_name'):
            if field_name in vals and vals[field_name]:
                vals[field_name] = vals[field_name].strip()

        # Normalize email, including empty and whitespace-only values.
        if 'email' in vals:
            email = (vals.get('email') or '').strip().lower()
            vals['email'] = email or False

        # Regular users cannot reassign patients to other users.
        if 'user_id' in vals and not is_manager:
            if vals['user_id'] != self.env.uid:
                raise ValidationError(
                    'You cannot reassign a patient to another user.'
                )

        # Medical record numbers are immutable after creation.
        if 'medical_record_number' in vals:
            raise ValidationError(
                'The medical record number cannot be changed.'
            )

        # Validate the requested status transition.
        self._check_state_transition(vals)

        # Validate department opening status and capacity.
        self._check_department_capacity(vals)

        return super().write(vals)

    # ==========================================
    # Patient Name Validation
    # ==========================================
    @api.constrains('first_name', 'last_name')
    def _check_patient_names(self):
        for record in self:
            if not (record.first_name or '').strip():
                raise ValidationError(
                    'First name cannot be empty.'
                )

            if not (record.last_name or '').strip():
                raise ValidationError(
                    'Last name cannot be empty.'
                )

    # ==========================================
    # Birth Date Validation
    # ==========================================
    @api.constrains('birth_date')
    def _check_birth_date(self):
        today = fields.Date.today()

        for record in self:
            if (
                record.birth_date
                and record.birth_date > today
            ):
                raise ValidationError(
                    'Birth date cannot be in the future.'
                )

    # ==========================================
    # Email Validation
    # ==========================================
    @api.constrains('email')
    def _check_email(self):
        email_pattern = (
            r'^[a-zA-Z0-9._%+-]+'
            r'@[a-zA-Z0-9.-]+'
            r'\.[a-zA-Z]{2,}$'
        )

        for record in self:
            if record.email and not re.match(
                email_pattern,
                record.email,
            ):
                raise ValidationError(
                    'Invalid email address.'
                )

    # ==========================================
    # CR Ratio Validation
    # ==========================================
    @api.constrains('cr_ratio')
    def _check_cr_ratio(self):
        for record in self:
            if record.cr_ratio < 0:
                raise ValidationError(
                    'CR Ratio cannot be negative.'
                )