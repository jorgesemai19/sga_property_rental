# -*- coding: utf-8 -*-
from odoo import models, fields

class RentalReport(models.Model):
    _name = "rental.report"
    _description = "Bloque de reportes"
    _order = "sequence, name"

    name = fields.Char("Título", required=True)
    sequence = fields.Integer("Orden", default=10)
    body = fields.Html("Contenido", sanitize=True)
    is_default = fields.Boolean("Seleccionada por defecto", default=False)
    is_editable = fields.Boolean("Permitir edición al usar", default=True)
    active = fields.Boolean(default=True)
