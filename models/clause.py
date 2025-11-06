# -*- coding: utf-8 -*-
from odoo import models, fields

class RentalClause(models.Model):
    _name = "rental.clause"
    _description = "Cláusula de contrato (plantilla)"
    _order = "sequence, name"

    name = fields.Char("Título", required=True)
    sequence = fields.Integer("Orden", default=10)
    body = fields.Html("Contenido", sanitize=True)
    is_default = fields.Boolean("Seleccionada por defecto", default=False)
    is_editable = fields.Boolean("Permitir edición al usar", default=True)
    active = fields.Boolean(default=True)
