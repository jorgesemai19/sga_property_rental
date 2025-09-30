# -*- coding: utf-8 -*-
from odoo import fields, models

class AccountMove(models.Model):
    _inherit = "account.move"

    rental_property_id = fields.Many2one("rental.property", "Propiedad")
    rental_contract_id = fields.Many2one("rental.contract", "Contrato (alquiler)")
    rental_contract_vendor_id = fields.Many2one("rental.contract", "Contrato (proveedor)")
