from odoo import models, fields, api


class Doctor(models.Model):
    _name = 'hms.doctors'
    _description = 'Hospital Doctor'
    _rec_name = 'name'
    _order = 'first_name, last_name'

    # =========================
    # Doctor Information
    # =========================
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
        string='Doctor Name',
        compute='_compute_name',
        store=True,
        index=True,
    )

    image = fields.Binary(
        string='Image',
        attachment=True,
    )

    # =========================
    # Compute Full Name
    # =========================
    @api.depends('first_name', 'last_name')
    def _compute_name(self):
        for doctor in self:
            first_name = (doctor.first_name or '').strip()
            last_name = (doctor.last_name or '').strip()

            doctor.name = ' '.join(
                part
                for part in (first_name, last_name)
                if part
            )