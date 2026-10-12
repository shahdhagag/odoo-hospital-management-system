from odoo import models, fields


class Doctor(models.Model):
    _name = 'hms.doctors'
    _description = 'Hospital Doctor'

    first_name = fields.Char(
        string='First Name',
        required=True
    )

    last_name = fields.Char(
        string='Last Name',
        required=True
    )

    image = fields.Binary(
        string='Image',
        attachment=True
    )

    def name_get(self):
        result = []

        for doctor in self:
            name = f"{doctor.first_name} {doctor.last_name}"
            result.append((doctor.id, name))

        return result