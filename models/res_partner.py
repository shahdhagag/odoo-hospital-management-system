from odoo import models, fields
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    related_patient_id = fields.Many2one(
        'hms.patient',
        string='Related Patient',
        ondelete='restrict',
    )

    def unlink(self):
        for record in self:
            if record.related_patient_id:
                raise ValidationError(
                    "You cannot delete a contact linked to a patient."
                )

        return super().unlink()