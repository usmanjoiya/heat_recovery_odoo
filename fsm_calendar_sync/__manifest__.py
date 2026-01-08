{
    'name': 'Field Service - Calendar Synchronization',
    'version': '19.0.1.0.0',
    'category': 'Services/Field Service',
    'summary': 'Automatic synchronization between Field Service tasks and Calendar events',
    'description': """
        Field Service Calendar Synchronization Module
        ==============================================

        This module provides seamless integration between Field Service tasks
        (project.task) and Calendar events (calendar.event) in Odoo.

        Key Features:
        - Automatic Calendar Event Creation for Field Service tasks
        - Real-time Synchronization on task updates
        - Strict Read-Only Enforcement on calendar events
        - Native Odoo Models (no custom tables)
        - Upgrade-safe ORM Overrides
        - Zero Manual User Interaction Required

        The synchronization is one-way (Task → Calendar) and guarantees data
        consistency, prevents manual conflicts, and improves operational visibility.
    """,
    'author': 'MountSol',
    'depends': [
        'project',
        'industry_fsm',
        'calendar',
    ],
    'data': [
        'views/project_task_views.xml',
        'views/calendar_event_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
