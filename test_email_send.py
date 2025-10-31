#!/usr/bin/env python3
"""
Quick test script for email sending
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# SMTP Configuration (same as in email_config.py)
SMTP_CONFIG = {
    'server': 'smtp.gmail.com',
    'port': 587,
    'use_tls': True,
    'username': 'gianluca.formica@colibridigital.io'
}

def test_email(password):
    """Test email sending with provided password."""

    # Create a simple test message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Test Email from ACE Report Hub'
    msg['From'] = 'gianluca.formica@colibridigital.io'
    msg['To'] = 'gianluca.formica@colibridigital.io'

    html_content = """
    <html>
    <body>
        <h2>Test Email</h2>
        <p>This is a test email from ACE Report Hub.</p>
        <p>If you're seeing this, the email configuration is working!</p>
    </body>
    </html>
    """

    msg.attach(MIMEText(html_content, 'html'))

    try:
        print(f"[TEST] Connecting to SMTP server: {SMTP_CONFIG['server']}:{SMTP_CONFIG['port']}")
        server = smtplib.SMTP(SMTP_CONFIG['server'], SMTP_CONFIG['port'])

        if SMTP_CONFIG['use_tls']:
            server.starttls()
            print(f"[TEST] TLS started")

        print(f"[TEST] Logging in as: {SMTP_CONFIG['username']}")
        server.login(SMTP_CONFIG['username'], password)
        print(f"[TEST] Login successful")

        print(f"[TEST] Sending email...")
        server.send_message(msg)
        print(f"[TEST] ✅ Email sent successfully!")
        server.quit()

        return True, "Email sent successfully"

    except smtplib.SMTPAuthenticationError as e:
        return False, f"Authentication failed: {str(e)}"
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        return False, f"Error: {str(e)}"

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python test_email_send.py <password>")
        sys.exit(1)

    password = sys.argv[1]
    success, message = test_email(password)

    if success:
        print(f"\n✅ SUCCESS: {message}")
    else:
        print(f"\n❌ FAILED: {message}")
