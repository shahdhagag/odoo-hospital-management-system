
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = 'res.partner'

    related_patient_id = fields.Many2one(
        'hms.patient',
        string='Related Patient'
    )

    @api.constrains('email')
    def _check_patient_email(self):
        for record in self:
            if record.email:
                patient = self.env['hms.patient'].search([
                    ('email', '=', record.email)
                ], limit=1)

                if patient:
                    raise ValidationError(
                        "This email already exists in Patient records."
                    )

    def unlink(self):
        for record in self:
            if record.related_patient_id:
                raise ValidationError(
                    "You cannot delete a customer linked to a patient."
                )

        return super(ResPartner, self).unlink()