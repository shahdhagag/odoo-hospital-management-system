{
    'name': 'Hospital HMS Customer',
    'version': '1.0',
    'depends': ['base', 'crm', 'account'],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'reports/patient_report.xml',
        'views/patient_views.xml',
        'views/department_views.xml',
        'views/doctor_views.xml',
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}