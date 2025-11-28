# -*- coding: utf-8 -*-
from datetime import timedelta

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

            # ⚠️ Convertimos de UTC a la zona horaria del usuario
            if slot.start_datetime:
                start_local = fields.Datetime.context_timestamp(
                    slot, slot.start_datetime
                )
                parts.append(start_local.strftime("%d/%m/%Y %H:%M"))

            if slot.end_datetime:
                end_local = fields.Datetime.context_timestamp(
                    slot, slot.end_datetime
                )
                parts.append("→ %s" % end_local.strftime("%H:%M"))

            slot.name = " - ".join([p for p in parts if p])

    @api.depends("state")
    def _compute_is_available(self):
        for slot in self:
            slot.is_available = slot.state == "available"

    @api.constrains("start_datetime", "end_datetime")
    def _check_datetimes(self):
        for slot in self:
            if (
                slot.start_datetime
                and slot.end_datetime
                and slot.end_datetime <= slot.start_datetime
            ):
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
        string="Contrato relacionado",
        domain="[('property_id', '=', property_id)]",
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
        domain="[('property_id', '=', property_id), "
               "('agent_id', '=', agent_id), "
               "('state', 'in', ('available', 'reserved'))]",
    )

    # AHORA: campos propios, no relacionados al slot
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
                start_local = fields.Datetime.context_timestamp(
                    visit, visit.start_datetime
                )
                parts.append(start_local.strftime("%d/%m/%Y %H:%M"))
            visit.name = " - ".join(parts)

    @api.onchange("slot_id")
    def _onchange_slot_id(self):
        for visit in self:
            if not visit.slot_id:
                continue

            slot = visit.slot_id

            # Sincronizamos propiedad y agente desde el slot, si aún no están fijados
            if not visit.property_id:
                visit.property_id = slot.property_id
            if not visit.agent_id:
                visit.agent_id = slot.agent_id

            # Si no hay hora aún, proponemos que inicie en el inicio de la franja
            if not visit.start_datetime:
                visit.start_datetime = slot.start_datetime

            # Por defecto proponemos 1 hora, pero nunca pasando el fin de la franja
            if not visit.end_datetime or visit.end_datetime <= visit.start_datetime:
                default_end = visit.start_datetime + timedelta(hours=1)
                if default_end > slot.end_datetime:
                    default_end = slot.end_datetime
                visit.end_datetime = default_end

    @api.constrains("start_datetime", "end_datetime", "slot_id", "agent_id", "state")
    def _check_visit_times(self):
        for visit in self:
            if not visit.start_datetime or not visit.end_datetime:
                continue

            if visit.start_datetime >= visit.end_datetime:
                raise ValidationError(
                    _("La hora de fin debe ser posterior a la hora de inicio.")
                )

            if visit.slot_id:
                s = visit.slot_id
                if visit.start_datetime < s.start_datetime or visit.end_datetime > s.end_datetime:
                    raise ValidationError(
                        _("La visita debe estar dentro de la franja del agente (%s - %s).")
                        % (s.start_datetime, s.end_datetime)
                    )

            # No permitir solapamiento con otras visitas del mismo agente
            domain = [
                ("id", "!=", visit.id),
                ("agent_id", "=", visit.agent_id.id),
                ("state", "in", ("requested", "confirmed", "done")),
                ("start_datetime", "<", visit.end_datetime),
                ("end_datetime", ">", visit.start_datetime),
            ]
            if self.search_count(domain):
                raise ValidationError(_("El agente ya tiene una visita en ese horario."))

    # -----------------------
    # Acciones de workflow
    # -----------------------
    def action_confirm(self):
        Slot = self.env["rental.visit.slot"]
        for visit in self:
            visit.state = "confirmed"

            slot = visit.slot_id
            if slot and slot.state in ("available", "reserved"):
                start = slot.start_datetime
                end = slot.end_datetime
                vs = visit.start_datetime
                ve = visit.end_datetime

                common_vals = {
                    "agent_id": slot.agent_id.id,
                    "property_id": slot.property_id.id,
                    "state": "available",
                }

                # Parte antes de la visita
                if vs > start:
                    Slot.create(dict(common_vals, start_datetime=start, end_datetime=vs))

                # Parte después de la visita
                if ve < end:
                    Slot.create(dict(common_vals, start_datetime=ve, end_datetime=end))

                # La franja original queda "booked" (ocupada por esta visita)
                slot.state = "booked"

    def action_cancel(self):
        Slot = self.env["rental.visit.slot"]
        for visit in self:
            # Creamos una franja libre exactamente en el horario de la visita
            if visit.agent_id and visit.property_id and visit.start_datetime and visit.end_datetime:
                Slot.create(
                    {
                        "agent_id": visit.agent_id.id,
                        "property_id": visit.property_id.id,
                        "start_datetime": visit.start_datetime,
                        "end_datetime": visit.end_datetime,
                        "state": "available",
                    }
                )

            visit.state = "cancelled"

    def action_mark_done(self):
        for visit in self:
            visit.state = "done"
            # La franja original ya quedó en booked, sirve como histórico
