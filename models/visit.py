# -*- coding: utf-8 -*-
from odoo import fields, models

class RentalVisit(models.Model):
    _name = "rental.visit"
    _description = "Visita a Propiedad"
    _order = "date desc"

    date = fields.Datetime("Fecha de visita", required=True, default=fields.Datetime.now)
    property_id = fields.Many2one("rental.property", "Propiedad", required=True)
    agent_id = fields.Many2one("res.partner", "Agente inmobiliario")
    interested_partner_id = fields.Many2one("res.partner", "Interesado")
    notes = fields.Text("Notas")
