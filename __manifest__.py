# -*- coding: utf-8 -*-
{
    "name": "SGA - Gestión de Alquileres",
    "summary": "Propiedades, contratos, visitas y facturación de alquileres",
    "version": "18.0.1.0.0",
    "author": "Jorge Maidana, Camila Maidana",
    "license": "LGPL-3",
    "category": "Real Estate",
    "depends": ["base", "web", "contacts", "account", "website_google_map"],
    "data": [
        "security/rental_security.xml",
        "security/ir.model.access.csv",

        "data/ir_sequence.xml",
        "data/ir_cron.xml",

        "views/property_views.xml",
        "views/contract_views.xml",
        "views/visit_views.xml",
        "views/account_move_views.xml",
        "views/clause_form_views.xml",   # aquí se define action_rental_clause
        "views/report_views.xml",
        "views/menu.xml",                # aquí se usa action_rental_clause
        "views/contract_report.xml",
        "views/schedule_client_views.xml",
        "views/website_product_extra_button.xml",
    ],
    "application": True,
}
