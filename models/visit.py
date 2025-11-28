# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class RentalVisitSlot(models.Model):
    _name = "rental.visit.slot"
    _description = "Franja horaria de visita"
    _order = "start_datetime"

    name = fields.Char("Descripción", compute="_compute_name", store=True)
    agent_id = fields.Many2one(
        "res.partner",
        string="Agente",
        required=True,
    )
    property_id = fields.Many2one(
        "rental.property",
        string="Propiedad",
        required=True,
    )
    start_datetime = fields.Datetime(
        string="Inicio",
        required=True,
    )
    end_datetime = fields.Datetime(
        string="Fin",
        required=True,
    )

    state = fields.Selection(
        [
            ("available", "Disponible"),
            ("reserved", "Reservado"),
            ("booked", "Confirmado"),
            ("blocked", "Bloqueado"),
        ],
        string="Estado",
        default="available",
        required=True,
    )

    visit_id = fields.One2many(
        "rental.visit",
        "slot_id",
        string="Visitas asociadas",
    )

    is_available = fields.Boolean(
        string="Disponible para portal",
        compute="_compute_is_available",
        store=False,
    )

    @api.depends("agent_id", "property_id", "start_datetime", "end_datetime")
    def _compute_name(self):
        for slot in self:
            parts = []
            if slot.property_id:
                parts.append(slot.property_id.name or "")
            if slot.agent_id:
                parts.append("Agente: %s" % (slot.agent_id.name,))
            if slot.start_datetime:
                parts.append(
                    slot.start_datetime.strftime("%d/%m/%Y %H:%M")
                )
            if slot.end_datetime:
                parts.append(
                    "→ %s" % slot.end_datetime.strftime("%H:%M")
                )
            slot.name = " - ".join([p for p in parts if p])

    @api.depends("state")
    def _compute_is_available(self):
        for slot in self:
            slot.is_available = slot.state == "available"

    @api.constrains("start_datetime", "end_datetime")
    def _check_datetimes(self):
        for slot in self:
            if slot.start_datetime and slot.end_datetime and slot.end_datetime <= slot.start_datetime:
                raise ValidationError(
                    _("La hora de fin debe ser posterior a la hora de inicio.")
                )


class RentalVisit(models.Model):
    _name = "rental.visit"
    _description = "Visita a propiedad"
    _order = "start_datetime desc, id desc"

    name = fields.Char("Referencia", compute="_compute_name", store=True)

    property_id = fields.Many2one(
        "rental.property",
        string="Propiedad",
        required=True,
    )
    contract_id = fields.Many2one(
        "rental.contract",
        string="Contrato relacionado (opcional)",
        domain="[('property_id', '=', property_id)]",
        required=False,
    )
    agent_id = fields.Many2one(
        "res.partner",
        string="Agente",
        required=True,
    )
    customer_id = fields.Many2one(
        "res.partner",
        string="Cliente / Interesado",
        required=True,
    )
    slot_id = fields.Many2one(
        "rental.visit.slot",
        string="Franja horaria",
        required=True,
        domain="[('property_id', '=', property_id), ('agent_id', '=', agent_id), ('state', 'in', ('available', 'reserved'))]",
    )

    start_datetime = fields.Datetime(
        string="Inicio",
        related="slot_id.start_datetime",
        store=True,
    )
    end_datetime = fields.Datetime(
        string="Fin",
        related="slot_id.end_datetime",
        store=True,
    )

    state = fields.Selection(
        [
            ("requested", "Solicitada"),
            ("confirmed", "Confirmada"),
            ("cancelled", "Cancelada"),
            ("done", "Realizada"),
        ],
        string="Estado",
        default="requested",
        required=True,
    )

    notes = fields.Text("Notas")

    @api.depends("property_id", "customer_id", "start_datetime")
    def _compute_name(self):
        for visit in self:
            parts = ["Visita"]
            if visit.property_id:
                parts.append(visit.property_id.name or "")
            if visit.customer_id:
                parts.append("(%s)" % visit.customer_id.name)
            if visit.start_datetime:
                parts.append(
                    visit.start_datetime.strftime("%d/%m/%Y %H:%M")
                )
            visit.name = " - ".join(parts)

    @api.onchange("slot_id")
    def _onchange_slot_id(self):
        for visit in self:
            if visit.slot_id:
                # Sincronizamos propiedad y agente desde el slot, si aún no están fijados
                if not visit.property_id:
                    visit.property_id = visit.slot_id.property_id
                if not visit.agent_id:
                    visit.agent_id = visit.slot_id.agent_id

    # -----------------------
    # Acciones de workflow
    # -----------------------
    def action_confirm(self):
        for visit in self:
            visit.state = "confirmed"
            if visit.slot_id and visit.slot_id.state in ("available", "reserved"):
                visit.slot_id.state = "booked"

    def action_cancel(self):
        for visit in self:
            visit.state = "cancelled"
            # Devolver la franja a disponible si estaba reservada/confirmada y la visita no se hizo
            if visit.slot_id and visit.slot_id.state in ("reserved", "booked"):
                # Opcionalmente, solo si la visita es futura
                visit.slot_id.state = "available"

    def action_mark_done(self):
        for visit in self:
            visit.state = "done"
            # La franja puede quedar como booked para histórico,
            # o podrías cambiarla a blocked si no querés que se reutilice.
