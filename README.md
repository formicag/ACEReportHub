# ACE Report Hub

**Modern Flask web app for AWS Partner Central ACE weekly hygiene reports**

## Features

- 📥 **Baseline Import** - One-time setup with your first ACE export
- 📊 **Weekly Reports** - Compare week-over-week changes automatically
- 📈 **Trend Tracking** - See improvements/declines in opportunity hygiene
- ✨ **Change Detection** - Automatically identifies new, closed, launched ops
- 📧 **Email Automation** - Generate and send HTML emails with one click
- 🧪 **Test Emails** - Test before sending to everyone
- 📜 **History** - View all past reports and trends
- 🔒 **Excluded Ops** - Track legacy ops separately (not included in reports)

## Setup

### 1. Activate Virtual Environment

```bash
cd /Users/gianlucaformica/Projects/ACEReportHub
source venv/bin/activate
```

### 2. Install Dependencies (if needed)

```bash
pip install -r requirements.txt
```

### 3. Start the Server

```bash
python app.py
```

### 4. Open in Browser

Navigate to: **http://localhost:5000**

## First Time Use

### Import Baseline

1. Click "Choose Baseline File"
2. Select your first ACE export (e.g., `Export (9).xlsx`)
3. Click "Import Baseline"
4. Wait for processing

This creates your first snapshot in the database.

## Weekly Workflow

### Every Friday:

1. Export latest ACE report from Partner Central
2. Save to `ACE-Reports/` folder
3. Open **http://localhost:5000**
4. Click "Choose ACE Export File"
5. Select this week's file
6. Click "Generate Report"
7. Review the summary (shows changes vs last week)
8. Click "Preview Email"
9. Enter your **App Password** (Google Workspace)
10. Click "Send Test Email" to test
11. If looks good, click "Send to All Recipients"

The app will:
- Send email to all stakeholders
- Save snapshot to database
- This becomes the baseline for next week

## Database

- **Location:** `ace_reports.db` (SQLite)
- **Tables:**
  - `weekly_snapshots` - Metadata for each sent report
  - `opportunities` - Full snapshot of all ops at each send
- **Automatic:** Created on first run

## Configuration

### Email Settings

Edit `email_config.py`:

```python
EMAIL_CONFIG = {
    'to': [...],  # Primary recipients
    'cc': [...],  # CC recipients
    'subject': 'ACE Hygiene',
    'from_email': 'your.email@domain.com'
}

SMTP_CONFIG = {
    'server': 'smtp.gmail.com',  # Gmail/Google Workspace
    'port': 587,
    'username': 'your.email@domain.com'
}
```

### Excluded Opportunities

Edit `ace_database.py` to modify `EXCLUDED_OPS` list:

```python
EXCLUDED_OPS = [
    'O18244',
    'O38038',
    # ... add more
]
```

These ops are:
- Tracked in database
- **Not** included in email reports
- Still counted in total stats

## Stopping the Server

Press `CTRL+C` in the terminal where the server is running.

## Troubleshooting

### "No module named 'flask'"

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Email Authentication Failed

- Use **App Password**, not regular password
- Create at: https://myaccount.google.com/apppasswords

### Port Already in Use

Change port in `app.py`:

```python
app.run(debug=True, port=5001)  # Use 5001 instead
```

## File Structure

```
ACEReportHub/
├── app.py                    # Main Flask application
├── ace_database.py          # Database operations
├── ace_processor.py         # ACE file processing
├── email_generator.py       # Email generation & sending
├── email_config.py          # Email configuration
├── templates/               # HTML templates
│   ├── index.html
│   ├── email_preview.html
│   └── history.html
├── static/
│   └── style.css            # Modern UI styles
├── ACE-Reports/             # Input files go here
├── ace_reports.db           # SQLite database
├── venv/                    # Virtual environment
└── requirements.txt         # Python dependencies
```

## Support

For issues:
1. Check console output where Flask is running
2. Check browser console (F12) for JavaScript errors
3. Verify email settings in `email_config.py`
4. Ensure ACE export files are in correct format

## Version

**v1.0** - Initial Flask release
