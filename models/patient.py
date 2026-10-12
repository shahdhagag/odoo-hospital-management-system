import re

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class Patient(models.Model):
    _name = 'hms.patient'
    _description = 'Hospital Patient'

    first_name = fields.Char(string='First Name')
    last_name = fields.Char(string='Last Name')
    birth_date = fields.Date(string='Birth Date')

    @api.constrains('birth_date')
    def _check_birth_date(self):
        for record in self:
            if record.birth_date and record.birth_date > fields.Date.today():
                raise ValidationError("Birth date cannot be in the future.")

    history = fields.Html(string='History')
    cr_ratio = fields.Float(string='CR Ratio')
    email = fields.Char(string='Email')
    _sql_constraints = [
        (
            'unique_patient_email',
            'UNIQUE(email)',
            'Patient email must be unique!'
        ),
    ]

    @api.constrains('email')
    def _check_email(self):
        for record in self:
            if record.email and not re.match(
                    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
                    record.email
            ):
                raise ValidationError("Invalid email address")

    blood_type = fields.Selection([
        ('a_positive', 'A+'),
        ('a_negative', 'A-'),
        ('b_positive', 'B+'),
        ('b_negative', 'B-'),
        ('ab_positive', 'AB+'),
        ('ab_negative', 'AB-'),
        ('o_positive', 'O+'),
        ('o_negative', 'O-'),
    ], string='Blood Type')

    pcr = fields.Boolean(string='PCR')
    image = fields.Binary(string='Image', attachment=True)
    address = fields.Text(string='Address')
    age = fields.Integer(
        string='Age',
        compute='_compute_age'
    )

    @api.depends('birth_date')
    def _compute_age(self):
        today = fields.Date.today()

        for record in self:
            if record.birth_date:
                record.age = today.year - record.birth_date.year

                if (today.month, today.day) < (record.birth_date.month, record.birth_date.day):
                    record.age -= 1
            else:
                record.age = 0

    department_id = fields.Many2one(
        'hms.department',
        string='Department'
    )

    doctor_ids = fields.Many2many(
        'hms.doctors',
        string='Doctors'
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user
    )