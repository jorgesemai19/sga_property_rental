# -*- coding: utf-8 -*-
{
    "name": "SGA Property Rental",
    "summary": "Gestión de alquileres para Inmobiliaria Emanuel",
    "version": "1.0",
    "author": "Jorge Maidana",
    "website": "",
    "category": "Custom",
    "license": "LGPL-3",
    "depends": [
        "base",
        "account",
        "sale",
        "contacts",
        "website_sale",
    ],
    "data": [
        "security/rental_security.xml",
        "security/ir.model.access.csv",

        "data/ir_sequence.xml",
        "data/ir_cron.xml",

        "views/property_views.xml",
        "views/contract_views.xml",
        "views/visit_views.xml",
        "views/account_move_views.xml",
        "views/clause_form_views.xml",
        "views/report_account_views.xml",
        "views/invoice_report_wizard_views.xml",
        "views/menu.xml",
        "views/contract_report.xml",
        "views/schedule_client_views.xml",
        "views/website_product_extra_button.xml",
    ],
    "installable": True,
    "application": True,
}
