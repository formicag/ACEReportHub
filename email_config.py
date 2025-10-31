#!/usr/bin/env python3
"""
Email Configuration for ACE Report
"""

# Email recipients configuration
EMAIL_CONFIG = {
    'to': [
        'Steve.Meek@nasstar.com',
        'Alan.Rowden@nasstar.com',
        'Tracy.Powell@nasstar.com',
        'John.Mansfield@nasstar.com',
        'Adam.Stephenson@nasstar.com',
        'charlie.saunders@colibridigital.io',
        'steven.sell@colibridigital.io',
        'lydia.cartwright@colibridigital.io',
        'jason.oliver@colibridigital.io',
    ],
    'cc': [
        'adam.dunn@colibridigital.io',
        'ben.wheeler@colibridigital.io',
        'julian.mallett@colibridigital.io',
        'marv.gillibrand@colibridigital.io',
    ],
    'subject': 'ACE Hygiene - New Report Format',
    'from_name': 'Gianluca Formica',
    'from_email': 'gianluca.formica@colibridigital.io'
}

# SMTP Configuration
# For Google Workspace (Gmail) - Use App Password when prompted
SMTP_CONFIG = {
    'server': 'smtp.gmail.com',  # For Google Workspace/Gmail
    'port': 587,  # TLS port
    'use_tls': True,
    'username': 'gianluca.formica@colibridigital.io',  # Your Google Workspace email
    'password': ''  # Will prompt for App Password at runtime (create at myaccount.google.com/apppasswords)
}

# Email body template
EMAIL_BODY_TEMPLATE = """Hi All,

The following projects have not been updated in over a month. To keep our score high on Partner Central ACE Ops need to be updated at least once a month or it impacts our score. Could you please add a next step etc. for each of your ops below? Or let me know if they need to be set closed.

{table}

Many thanks.

Kind regards,
Gianluca"""

# Threshold for opportunities to include (days since last update)
DAYS_THRESHOLD = 30
