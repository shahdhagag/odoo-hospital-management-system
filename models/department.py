from odoo import models, fields, api
from odoo.exceptions import ValidationError


class Department(models.Model):
    _name = 'hms.department'
    _description = 'Hospital Department'
    _rec_name = 'name'
    _order = 'name'

    # ==========================================
    # Basic Information
    # ==========================================
    name = fields.Char(
        string='Name',
        required=True,
    )

    capacity = fields.Integer(
        string='Capacity',
        required=True,
        default=10,
    )

    is_opened = fields.Boolean(
        string='Is Opened',
        default=True,
    )

    closure_reason = fields.Text(
        string='Closure Reason',
    )

    opened_date = fields.Date(
        string='Opening Date',
        readonly=True,
        copy=False,
    )

    closed_date = fields.Date(
        string='Closing Date',
        readonly=True,
        copy=False,
    )

    # ==========================================
    # Patient Relations
    # ==========================================
    patient_ids = fields.One2many(
        'hms.patient',
        'department_id',
        string='Patients',
    )

    patient_count = fields.Integer(
        string='Total Patients',
        compute='_compute_patient_count',
    )

    admitted_patient_count = fields.Integer(
        string='Admitted Patients',
        compute='_compute_admitted_patient_count',
    )

    remaining_capacity = fields.Integer(
        string='Remaining Capacity',
        compute='_compute_capacity_information',
    )

    occupancy_percentage = fields.Float(
        string='Occupancy Percentage',
        compute='_compute_capacity_information',
        digits=(5, 2),
    )

    is_nearly_full = fields.Boolean(
        string='Nearly Full',
        compute='_compute_capacity_information',
    )

    # ==========================================
    # SQL Constraints
    # ==========================================
    _sql_constraints = [
        (
            'unique_department_name',
            'UNIQUE(name)',
            'Department name must be unique!',
        ),
        (
            'positive_department_capacity',
            'CHECK(capacity >= 0)',
            'Department capacity cannot be negative!',
        ),
    ]

    # ==========================================
    # Patient Count
    # ==========================================
    @api.depends('patient_ids')
    def _compute_patient_count(self):
        for department in self:
            department.patient_count = len(
                department.patient_ids
            )

    # ==========================================
    # Admitted Patient Count
    # ==========================================
    @api.depends('patient_ids.state')
    def _compute_admitted_patient_count(self):
        for department in self:
            department.admitted_patient_count = len(
                department.patient_ids.filtered(
                    lambda patient: patient.state == 'admitted'
                )
            )

    # ==========================================
    # Capacity Information
    # ==========================================
    @api.depends(
        'capacity',
        'admitted_patient_count',
    )
    def _compute_capacity_information(self):
        for department in self:
            capacity = department.capacity
            admitted = department.admitted_patient_count

            department.remaining_capacity = max(
                capacity - admitted,
                0,
            )

            department.occupancy_percentage = (
                admitted / capacity * 100
                if capacity > 0
                else 0
            )

            department.is_nearly_full = (
                capacity > 0
                and admitted / capacity >= 0.8
            )

    # ==========================================
    # Capacity Validation
    # ==========================================
    @api.constrains('capacity')
    def _check_capacity(self):
        Patient = self.env['hms.patient'].sudo()

        for department in self:
            admitted_count = Patient.search_count([
                ('department_id', '=', department.id),
                ('state', '=', 'admitted'),
            ])

            if admitted_count > department.capacity:
                raise ValidationError(
                    'Capacity cannot be lower than the current '
                    'number of admitted patients.'
                )

    # ==========================================
    # Department Name Validation
    # ==========================================
    @api.constrains('name')
    def _check_department_name(self):
        for department in self:
            if not (department.name or '').strip():
                raise ValidationError(
                    'Department name cannot be empty.'
                )

    # ==========================================
    # Create Department
    # ==========================================
    @api.model_create_multi
    def create(self, vals_list):
        today = fields.Date.today()

        # Avoid modifying the caller's dictionaries.
        vals_list = [
            vals.copy()
            for vals in vals_list
        ]

        for vals in vals_list:
            # Normalize the department name.
            if vals.get('name'):
                vals['name'] = vals['name'].strip()

            # Opening and closing dates are system-managed.
            vals.pop('opened_date', None)
            vals.pop('closed_date', None)

            is_opened = vals.get('is_opened', True)

            if is_opened:
                vals['opened_date'] = today
                vals['closed_date'] = False
                vals['closure_reason'] = False

            else:
                closure_reason = (
                    vals.get('closure_reason') or ''
                ).strip()

                if not closure_reason:
                    raise ValidationError(
                        'Please provide a reason for closing '
                        'the department.'
                    )

                vals['closure_reason'] = closure_reason
                vals['opened_date'] = False
                vals['closed_date'] = today

        return super().create(vals_list)

    # ==========================================
    # Update Department
    # ==========================================
    def write(self, vals):
        vals = vals.copy()
        today = fields.Date.today()

        # Opening and closing dates cannot be edited manually.
        vals.pop('opened_date', None)
        vals.pop('closed_date', None)

        # Normalize the department name.
        if vals.get('name'):
            vals['name'] = vals['name'].strip()

        # Handle closing the department.
        if vals.get('is_opened') is False:
            closure_reason = (
                vals.get('closure_reason')
                or (
                    self.closure_reason
                    if len(self) == 1
                    else ''
                )
                or ''
            ).strip()

            if not closure_reason:
                raise ValidationError(
                    'Please provide a reason for closing '
                    'the department.'
                )

            # Do not close a department with admitted patients.
            Patient = self.env['hms.patient'].sudo()

            for department in self:
                admitted_count = Patient.search_count([
                    ('department_id', '=', department.id),
                    ('state', '=', 'admitted'),
                ])

                if admitted_count:
                    raise ValidationError(
                        'You cannot close department %s while it '
                        'has admitted patients. Discharge or move '
                        'the patients first.'
                        % department.name
                    )

            vals['closure_reason'] = closure_reason

            for department in self:
                if department.is_opened:
                    vals['closed_date'] = today

        # Handle reopening the department.
        elif vals.get('is_opened') is True:
            vals['closed_date'] = False
            vals['closure_reason'] = False

            for department in self:
                if not department.opened_date:
                    vals['opened_date'] = today

        return super().write(vals)

    # ==========================================
    # Prevent Deleting Assigned Departments
    # ==========================================
    def unlink(self):
        for department in self:
            if department.patient_ids:
                raise ValidationError(
                    'You cannot delete a department that has '
                    'patients assigned to it.'
                )

        return super().unlink()