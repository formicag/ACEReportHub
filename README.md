# ACE Report Hub

**Automated weekly ACE hygiene reporting system for AWS Partner Central**

A Flask-based web application that processes AWS Partner Central ACE (Account Coverage Engine) export files, tracks opportunity hygiene metrics, and generates automated weekly email reports with AI-powered summaries.

---

## Features

### Core Functionality
- **Baseline Import**: Import your first ACE export to establish a baseline
- **Weekly Processing**: Upload weekly ACE exports to track changes
- **Comparison Engine**: Automatically compare current week vs baseline to identify:
  - New opportunities
  - Closed opportunities
  - Status changes
- **Stale Opportunity Detection**: Flag opportunities with no updates in 30+ days
- **Email Automation**: Generate and send HTML email reports via SMTP

### AI-Powered Insights
- **AWS Bedrock Integration**: AI-generated executive summaries using Claude
- **Automated Analysis**: Key insights, trends, and recommendations
- **Context-Aware**: Includes Well-Architected and RAPID PILOT opportunity tracking

### Data Management
- **SQLite Database**: Local data storage with full history
- **Snapshot System**: Weekly snapshots for historical tracking
- **Audit Logging**: Comprehensive audit trail for all actions
- **Data Lineage**: Track source files and transformations

### Advanced Features
- **Validation System**: Configurable data validation rules (currently disabled)
- **Email Distribution Management**: Web-based recipient list management
- **Duplicate Detection**: Prevents saving duplicate weekly reports
- **Legacy Opportunity Exclusion**: 13 legacy opportunities automatically excluded from reports

---

## Technology Stack

- **Backend**: Python 3.x, Flask
- **Database**: SQLite3
- **Excel Processing**: pandas, openpyxl
- **AI**: AWS Bedrock (Claude)
- **Email**: SMTP with Gmail App Passwords
- **Frontend**: HTML, CSS, JavaScript (vanilla)

---

## Installation

### Prerequisites
- Python 3.8+
- AWS Account with Bedrock access (for AI summaries)
- Gmail account with App Password (for email sending)

### Setup

1. **Clone the repository**
   \`\`\`bash
   git clone <repository-url>
   cd ACEReportHub
   \`\`\`

2. **Create virtual environment**
   \`\`\`bash
   python3 -m venv venv
   source venv/bin/activate  # On macOS/Linux
   # or
   venv\Scripts\activate  # On Windows
   \`\`\`

3. **Install dependencies**
   \`\`\`bash
   pip install -r requirements.txt
   \`\`\`

4. **Configure AWS Credentials**
   - Set up AWS CLI with credentials that have Bedrock access
   - Ensure the \`us-east-1\` region is configured

5. **Configure Email**
   - Edit \`email_config.py\` to set your email addresses
   - Generate a Gmail App Password: https://myaccount.google.com/apppasswords

6. **Run the application**
   \`\`\`bash
   python app.py
   \`\`\`

7. **Open in browser**
   \`\`\`
   http://localhost:5001
   \`\`\`

---

## Usage

### First Time Setup

1. **Import Baseline**
   - Navigate to the dashboard
   - Click "Choose Baseline File"
   - Select your ACE export (.xlsx file)
   - Enter the report week date (the Monday of that week)
   - Click "Import Baseline"

### Weekly Workflow

1. **Upload Weekly Report**
   - Export ACE report from AWS Partner Central
   - Upload via "Generate Weekly Report" section
   - Enter the report week date

2. **Preview Email**
   - Review the generated email with:
     - AI summary
     - Stale opportunities list
     - Comparison with baseline (new/closed/changed)
     - Key metrics

3. **Save Report** (Optional)
   - Save snapshot to database for historical tracking
   - Prevents duplicate saves for the same week

4. **Send Email**
   - Enter your Gmail App Password
   - Click "Send to All Recipients"
   - Or use "Send Test Email" to send to yourself first

---

## File Structure

\`\`\`
ACEReportHub/
├── app.py                      # Main Flask application
├── ace_database.py             # Database management and queries
├── ace_processor.py            # ACE file processing logic
├── email_generator.py          # Email HTML generation
├── email_config.py             # Email distribution lists
├── bedrock_service.py          # AWS Bedrock AI integration
├── audit_logger.py             # Comprehensive audit logging
├── validation_rules.py         # Data validation engine (disabled)
├── templates/
│   ├── index.html              # Main dashboard
│   ├── email_preview.html      # Email preview page
│   ├── history.html            # Snapshot history viewer
│   └── validation_errors.html  # Validation error viewer
├── static/
│   └── style.css               # Application styles
├── ACE-Reports/                # Uploaded ACE files
├── temp_emails/                # Generated email HTML files
├── ace_reports.db              # SQLite database
└── requirements.txt            # Python dependencies
\`\`\`

---

## Configuration

### Email Distribution (\`email_config.py\`)

\`\`\`python
EMAIL_CONFIG = {
    'to': [
        'recipient1@example.com',
        'recipient2@example.com',
    ],
    'cc': [
        'cc@example.com',
    ],
    'from_email': 'sender@example.com',
    'from_name': 'ACE Report Bot'
}
\`\`\`

### Excluded Opportunities (\`ace_database.py\`)

13 legacy opportunities are automatically excluded from reports. Edit \`EXCLUDED_OPS\` list to modify.

### Stale Threshold (\`email_config.py\`)

Default: 30 days. Opportunities with no update for 30+ days are flagged as stale.

---

## Database Schema

### Main Tables
- **snapshots**: Weekly snapshot metadata
- **opportunities**: Individual opportunity records
- **snapshot_opportunities**: Links opportunities to snapshots
- **audit_log**: Comprehensive event logging
- **data_lineage**: Source file tracking
- **validation_rules**: Configurable validation rules
- **validation_results**: Validation execution results

---

## Security Notes

- Never commit \`email_config.py\` with real email addresses to public repos
- Gmail App Passwords should be stored securely (use environment variables in production)
- AWS credentials should follow least-privilege principle
- Database contains sensitive business data - secure accordingly

---

## Known Issues & TODOs

- Validation system currently disabled (needs context-aware rules)
- No authentication/authorization (single-user system)
- Email templates are not customizable via UI
- No export functionality for historical data

---

## License

Internal tool - Not licensed for external use

---

## Author

Built with Claude Code by Anthropic

---

## Support

For issues or questions, please create a GitHub issue or contact the development team.
