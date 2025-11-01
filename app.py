#!/usr/bin/env python3
"""
ACE Report Hub - Flask Application
Weekly ACE report processing and email automation
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
from datetime import datetime
from werkzeug.utils import secure_filename
import uuid
import sys

from ace_database import ACEDatabase, EXCLUDED_OPS
from ace_processor import process_ace_file, get_stale_opportunities
from email_generator import create_email_message, send_email, generate_email_html
from email_config import DAYS_THRESHOLD
from validation_rules import ValidationEngine

# ULTRA FINE LOGGING - Force to stderr so it shows even in debug mode
def log(msg):
    print(msg, file=sys.stderr, flush=True)

app = Flask(__name__)
app.secret_key = 'ace-report-hub-secret-key-change-in-production'
app.config['UPLOAD_FOLDER'] = 'ACE-Reports'
app.config['TEMP_EMAIL_FOLDER'] = 'temp_emails'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create temp email folder if it doesn't exist
os.makedirs(app.config['TEMP_EMAIL_FOLDER'], exist_ok=True)

# Initialize database and validation engine
db = ACEDatabase()
validator = ValidationEngine('ace_reports.db')


@app.route('/')
def index():
    """Main dashboard page."""
    has_baseline = db.has_baseline()
    last_snapshot = db.get_last_snapshot() if has_baseline else None
    all_snapshots = db.get_all_snapshots() if has_baseline else []

    return render_template('index.html',
                         has_baseline=has_baseline,
                         last_snapshot=last_snapshot,
                         all_snapshots=all_snapshots,
                         excluded_ops_count=len(EXCLUDED_OPS))


@app.route('/upload_baseline', methods=['POST'])
def upload_baseline():
    """Handle baseline file upload."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400

    if file and file.filename.endswith('.xlsx'):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            # Check if baseline already exists
            if db.has_baseline():
                return jsonify({
                    'success': False,
                    'error': 'Baseline already exists! If you want to reimport, please delete ace_reports.db first.'
                }), 400

            # Get report week date from form
            report_week_date = request.form.get('report_week_date')
            if not report_week_date:
                return jsonify({'success': False, 'error': 'Report week date is required'}), 400

            # Process the file
            result = process_ace_file(filepath)
            df_all = result['df_all']
            stats = result['stats']

            log(f"[UPLOAD_BASELINE] Report week date: {report_week_date}")

            # Save as baseline snapshot
            snapshot_id = db.save_snapshot(
                df_all=df_all,
                snapshot_date=datetime.now(),
                ace_filename=filename,
                ace_file_date=stats['file_date'],
                notes="Baseline snapshot",
                report_week_date=report_week_date
            )

            return jsonify({
                'success': True,
                'message': f'Baseline saved! {stats["total_open"]} opportunities imported.',
                'snapshot_id': snapshot_id,
                'stats': {
                    'total_open': stats['total_open'],
                    'avg_days': stats['avg_days_since_update'],
                    'stale_count': stats['stale_count']
                }
            })

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    return jsonify({'success': False, 'error': 'Invalid file type'}), 400


@app.route('/upload_weekly', methods=['POST'])
def upload_weekly():
    """Handle weekly ACE file upload and processing."""
    print("\n" + "="*80)
    print("[UPLOAD_WEEKLY] STARTING")
    print("="*80)

    if 'file' not in request.files:
        print("[UPLOAD_WEEKLY] ERROR: No file in request")
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400

    file = request.files['file']
    print(f"[UPLOAD_WEEKLY] File received: {file.filename}")

    if file.filename == '':
        print("[UPLOAD_WEEKLY] ERROR: Empty filename")
        return jsonify({'success': False, 'error': 'No file selected'}), 400

    # Get report week date from form
    report_week_date = request.form.get('report_week_date')
    if not report_week_date:
        return jsonify({'success': False, 'error': 'Report week date is required'}), 400

    log(f"[UPLOAD_WEEKLY] *** REPORT WEEK DATE FROM FORM: {report_week_date} ***")

    if file and file.filename.endswith('.xlsx'):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        print(f"[UPLOAD_WEEKLY] Saving file to: {filepath}")
        file.save(filepath)
        print(f"[UPLOAD_WEEKLY] File saved successfully")

        try:
            # Process the file
            print("[UPLOAD_WEEKLY] Step 1: Processing ACE file...")
            result = process_ace_file(filepath)
            print(f"[UPLOAD_WEEKLY] Step 1 DONE: Processed {len(result['df_all'])} total ops")

            df_all = result['df_all']
            df_open = result['df_open']  # OPEN ops only (for reporting)
            stats = result['stats']
            print(f"[UPLOAD_WEEKLY] Open ops: {len(df_open)}, Stats: {stats}")

            # TODO: Add proper context-aware validation
            # Validation should be different for: import files vs comparison reports
            # Currently disabled until rules are properly configured
            # print("[UPLOAD_WEEKLY] Step 1.5: Validation temporarily disabled")

            # Get stale opportunities FROM OPEN OPS ONLY
            print(f"[UPLOAD_WEEKLY] Step 2: Getting stale ops (threshold: {DAYS_THRESHOLD} days)...")
            df_stale = get_stale_opportunities(df_open, DAYS_THRESHOLD)
            print(f"[UPLOAD_WEEKLY] Step 2 DONE: Found {len(df_stale)} stale ops")

            # Filter out excluded ops for reportable counts
            print(f"[UPLOAD_WEEKLY] Step 3: Filtering excluded ops ({len(EXCLUDED_OPS)} excluded)...")
            df_reportable = df_open[~df_open['Opportunity id'].isin(EXCLUDED_OPS)]
            df_stale_reportable = df_stale[~df_stale['Opportunity id'].isin(EXCLUDED_OPS)]
            print(f"[UPLOAD_WEEKLY] Step 3 DONE: Reportable: {len(df_reportable)}, Stale reportable: {len(df_stale_reportable)}")

            # Compare with BASELINE snapshot (ALWAYS the first one, never same-day uploads)
            print("[UPLOAD_WEEKLY] Step 4: Getting BASELINE snapshot for comparison...")
            comparison_data = None
            previous_stats = None
            baseline_snapshot = db.get_baseline_snapshot()
            print(f"[UPLOAD_WEEKLY] Baseline snapshot exists: {baseline_snapshot is not None}")

            if baseline_snapshot:
                # USE report_week_date if available, otherwise fall back to snapshot_date
                baseline_week_date_str = baseline_snapshot.get('report_week_date')
                if baseline_week_date_str:
                    baseline_date = datetime.strptime(baseline_week_date_str, '%Y-%m-%d').date()
                else:
                    baseline_date = datetime.fromisoformat(baseline_snapshot['snapshot_date']).date()

                # CRITICAL FIX: Use report_week_date from form, NOT datetime.now()!
                current_week_date = datetime.strptime(report_week_date, '%Y-%m-%d').date()

                log("="*100)
                log("[UPLOAD_WEEKLY] *** COMPARISON VALIDATION ***")
                log(f"[UPLOAD_WEEKLY] Baseline report:")
                log(f"[UPLOAD_WEEKLY]   - Snapshot ID: {baseline_snapshot['snapshot_id']}")
                log(f"[UPLOAD_WEEKLY]   - File: {baseline_snapshot['ace_export_filename']}")
                log(f"[UPLOAD_WEEKLY]   - Report Week Date: {baseline_date}")
                log(f"[UPLOAD_WEEKLY] Current report:")
                log(f"[UPLOAD_WEEKLY]   - File: {filename}")
                log(f"[UPLOAD_WEEKLY]   - Report Week Date: {current_week_date} (from form)")
                log(f"[UPLOAD_WEEKLY] Same day? {baseline_date == current_week_date}")
                log("="*100)

                if baseline_date == current_week_date:
                    log("[UPLOAD_WEEKLY] ⚠️ WARNING: Cannot compare - both reports from same day!")
                    log("[UPLOAD_WEEKLY] Comparison will be SKIPPED to prevent zero-delta bug")
                    comparison_data = None
                    previous_stats = None
                else:
                    days_apart = (current_week_date - baseline_date).days
                    log(f"[UPLOAD_WEEKLY] ✓ Valid comparison: {days_apart} days apart")
                    log("[UPLOAD_WEEKLY] Step 5: Comparing with BASELINE snapshot...")
                    comparison_data = db.compare_snapshots(df_all, baseline_snapshot['snapshot_id'])
                    previous_stats = baseline_snapshot
                    log(f"[UPLOAD_WEEKLY] Step 5 DONE: New: {len(comparison_data['new_ops'])}, Closed: {len(comparison_data['closed_ops'])}")

            # Calculate consecutive weeks with no stale ops for preview
            print("[UPLOAD_WEEKLY] Step 6: Calculating consecutive weeks...")
            consecutive_weeks = 0
            if len(df_stale_reportable) == 0:
                if baseline_snapshot and baseline_snapshot.get('consecutive_weeks_no_stale'):
                    consecutive_weeks = baseline_snapshot['consecutive_weeks_no_stale'] + 1
                else:
                    consecutive_weeks = 1
            print(f"[UPLOAD_WEEKLY] Step 6 DONE: Consecutive weeks with no stale: {consecutive_weeks}")

            # Store in session for email preview
            print("[UPLOAD_WEEKLY] Step 7: Storing in session...")
            print("=" * 100)
            print("[UPLOAD_WEEKLY] *** STATS FROM ACE_PROCESSOR ***")
            print(f"[UPLOAD_WEEKLY] Stats keys: {list(stats.keys())}")
            print(f"[UPLOAD_WEEKLY] Full stats dict: {stats}")
            print(f"[UPLOAD_WEEKLY] WA count from processor: {stats.get('well_architected_count', 'KEY NOT FOUND')}")
            print(f"[UPLOAD_WEEKLY] RAPID count from processor: {stats.get('rapid_pilot_count', 'KEY NOT FOUND')}")
            print("=" * 100)

            session['current_file'] = filepath
            session['current_filename'] = filename
            session['report_week_date'] = report_week_date  # STORE DATE IN SESSION FOR SEND_EMAIL
            log(f"[UPLOAD_WEEKLY] *** STORED report_week_date IN SESSION: {report_week_date} ***")
            session['stats'] = {
                'total_open_ops': len(df_all),
                'total_reportable_ops': len(df_reportable),
                'total_excluded_ops': len(df_all) - len(df_reportable),
                'avg_days_since_update': stats['avg_days_since_update'],
                'stale_ops_count': len(df_stale_reportable),
                'total_arr': stats['total_arr'],  # ADD ARR
                'well_architected_count': stats['well_architected_count'],  # CRITICAL - for Bedrock
                'rapid_pilot_count': stats['rapid_pilot_count'],  # CRITICAL - for Bedrock
                'consecutive_weeks_no_stale': consecutive_weeks,
                'processed_date': datetime.now().isoformat()
            }
            print("=" * 100)
            print("[UPLOAD_WEEKLY] *** SAVED TO SESSION ***")
            print(f"[UPLOAD_WEEKLY] Session stats keys: {list(session['stats'].keys())}")
            print(f"[UPLOAD_WEEKLY] Session stats: {session['stats']}")
            print(f"[UPLOAD_WEEKLY] Session WA count: {session['stats']['well_architected_count']}")
            print(f"[UPLOAD_WEEKLY] Session RAPID count: {session['stats']['rapid_pilot_count']}")
            print("=" * 100)
            print(f"[UPLOAD_WEEKLY] Step 7 DONE: Session updated with WA count={stats['well_architected_count']}, RAPID count={stats['rapid_pilot_count']}")

            response = {
                'success': True,
                'message': 'Report processed successfully!',
                'stats': session['stats'],
                'previous_stats': previous_stats,
                'comparison': {
                    'new_ops_count': len(comparison_data['new_ops']) if comparison_data else 0,
                    'closed_ops_count': len(comparison_data['closed_ops']) if comparison_data else 0,
                    'status_changes_count': len(comparison_data['status_changes']) if comparison_data else 0
                } if comparison_data else None
            }
            print("[UPLOAD_WEEKLY] ✅ SUCCESS - Returning response")
            print("="*80 + "\n")
            return jsonify(response)

        except Exception as e:
            print(f"[UPLOAD_WEEKLY] ❌ EXCEPTION: {type(e).__name__}: {str(e)}")
            import traceback
            print(f"[UPLOAD_WEEKLY] FULL TRACEBACK:\n{traceback.format_exc()}")
            print("="*80 + "\n")
            return jsonify({'success': False, 'error': str(e)}), 500

    print("[UPLOAD_WEEKLY] ERROR: Invalid file type (not .xlsx)")
    print("="*80 + "\n")
    return jsonify({'success': False, 'error': 'Invalid file type'}), 400


@app.route('/preview_email')
def preview_email():
    """Preview email before sending."""
    print("\n" + "🔥🔥🔥" * 30)
    print("[PREVIEW_EMAIL] ==================== ROUTE ENTERED ====================")
    print("[PREVIEW_EMAIL] STARTING PREVIEW EMAIL GENERATION")
    print("[PREVIEW_EMAIL] Time:", datetime.now().isoformat())
    print("🔥🔥🔥" * 30)
    print("\n" + "="*80)
    print("[PREVIEW_EMAIL] STARTING")
    print("="*80)

    print("[PREVIEW_EMAIL] LINE 293: Checking session for 'current_file'")
    print(f"[PREVIEW_EMAIL] LINE 294: session type = {type(session)}")
    print(f"[PREVIEW_EMAIL] LINE 295: session keys = {list(session.keys())}")
    print(f"[PREVIEW_EMAIL] LINE 296: Full session contents:")
    for key in session.keys():
        print(f"[PREVIEW_EMAIL] LINE 297:   session['{key}'] = {session[key]}")

    print(f"[PREVIEW_EMAIL] LINE 299: Checking if 'current_file' in session")
    has_current_file = ('current_file' in session)
    print(f"[PREVIEW_EMAIL] LINE 301: 'current_file' in session = {has_current_file}")

    if 'current_file' not in session:
        print("[PREVIEW_EMAIL] ERROR: No current_file in session")
        return "No report generated yet. Please upload a weekly file first.", 400

    print(f"[PREVIEW_EMAIL] LINE 306: current_file IS in session")
    print(f"[PREVIEW_EMAIL] Current file: {session['current_file']}")

    try:
        # Load current data
        print("[PREVIEW_EMAIL] Step 1: Processing ACE file...")
        result = process_ace_file(session['current_file'])
        print(f"[PREVIEW_EMAIL] Step 1 DONE: Got {len(result['df_all'])} total ops")

        df_all = result['df_all']
        df_open = result['df_open']  # OPEN ops only
        print(f"[PREVIEW_EMAIL] Step 2: Getting stale opportunities from {len(df_open)} open ops...")
        df_stale = get_stale_opportunities(df_open, DAYS_THRESHOLD)
        print(f"[PREVIEW_EMAIL] Step 2 DONE: Found {len(df_stale)} stale ops")

        # Get comparison data from BASELINE snapshot
        print("[PREVIEW_EMAIL] Step 3: Getting comparison data from BASELINE...")
        comparison_data = None
        previous_stats = None
        baseline_snapshot = db.get_baseline_snapshot()
        print(f"[PREVIEW_EMAIL] Step 3: Baseline snapshot exists: {baseline_snapshot is not None}")

        if baseline_snapshot:
            print("[PREVIEW_EMAIL] LINE 318: baseline_snapshot EXISTS - entering comparison logic")
            print(f"[PREVIEW_EMAIL] LINE 318: baseline_snapshot type = {type(baseline_snapshot)}")
            print(f"[PREVIEW_EMAIL] LINE 318: baseline_snapshot keys = {list(baseline_snapshot.keys()) if isinstance(baseline_snapshot, dict) else 'NOT A DICT'}")

            # CRITICAL FIX: Use report_week_date for comparison, NOT snapshot_date!
            # Same fix we did for upload_weekly
            print("[PREVIEW_EMAIL] LINE 322: About to get report_week_date from baseline_snapshot")

            # Get baseline report week date
            print("[PREVIEW_EMAIL] LINE 325: Calling baseline_snapshot.get('report_week_date')")
            baseline_week_date_str = baseline_snapshot.get('report_week_date')
            print(f"[PREVIEW_EMAIL] LINE 326: baseline_week_date_str = '{baseline_week_date_str}'")
            print(f"[PREVIEW_EMAIL] LINE 327: baseline_week_date_str type = {type(baseline_week_date_str)}")
            print(f"[PREVIEW_EMAIL] LINE 328: baseline_week_date_str is None? {baseline_week_date_str is None}")
            print(f"[PREVIEW_EMAIL] LINE 329: baseline_week_date_str is empty string? {baseline_week_date_str == ''}")
            print(f"[PREVIEW_EMAIL] LINE 330: bool(baseline_week_date_str) = {bool(baseline_week_date_str)}")

            if baseline_week_date_str:
                print(f"[PREVIEW_EMAIL] LINE 332: baseline_week_date_str IS TRUTHY - parsing date")
                print(f"[PREVIEW_EMAIL] LINE 333: Calling datetime.strptime('{baseline_week_date_str}', '%Y-%m-%d')")
                baseline_date = datetime.strptime(baseline_week_date_str, '%Y-%m-%d').date()
                print(f"[PREVIEW_EMAIL] LINE 335: baseline_date = {baseline_date}")
                print(f"[PREVIEW_EMAIL] LINE 336: baseline_date type = {type(baseline_date)}")
            else:
                print(f"[PREVIEW_EMAIL] LINE 338: baseline_week_date_str IS FALSY - using fallback")
                # Fallback to snapshot_date if report_week_date not available
                print(f"[PREVIEW_EMAIL] LINE 340: Getting snapshot_date as fallback")
                snapshot_date_value = baseline_snapshot['snapshot_date']
                print(f"[PREVIEW_EMAIL] LINE 342: snapshot_date value = '{snapshot_date_value}'")
                baseline_date = datetime.fromisoformat(snapshot_date_value).date()
                print(f"[PREVIEW_EMAIL] LINE 344: baseline_date (from snapshot_date) = {baseline_date}")

            print("[PREVIEW_EMAIL] LINE 346: Now getting current report week date from session")
            # Get current report week date from session (uploaded file's report_week_date)
            print("[PREVIEW_EMAIL] LINE 348: Calling session.get('report_week_date')")
            current_week_date_str = session.get('report_week_date')
            print(f"[PREVIEW_EMAIL] LINE 350: current_week_date_str = '{current_week_date_str}'")
            print(f"[PREVIEW_EMAIL] LINE 351: current_week_date_str type = {type(current_week_date_str)}")
            print(f"[PREVIEW_EMAIL] LINE 352: current_week_date_str is None? {current_week_date_str is None}")
            print(f"[PREVIEW_EMAIL] LINE 353: current_week_date_str is empty string? {current_week_date_str == ''}")
            print(f"[PREVIEW_EMAIL] LINE 354: bool(current_week_date_str) = {bool(current_week_date_str)}")

            if current_week_date_str:
                print(f"[PREVIEW_EMAIL] LINE 356: current_week_date_str IS TRUTHY - parsing date")
                print(f"[PREVIEW_EMAIL] LINE 357: Calling datetime.strptime('{current_week_date_str}', '%Y-%m-%d')")
                current_date = datetime.strptime(current_week_date_str, '%Y-%m-%d').date()
                print(f"[PREVIEW_EMAIL] LINE 359: current_date = {current_date}")
                print(f"[PREVIEW_EMAIL] LINE 360: current_date type = {type(current_date)}")
            else:
                print(f"[PREVIEW_EMAIL] LINE 362: current_week_date_str IS FALSY - using datetime.now()")
                # Fallback to today if report_week_date not in session
                print(f"[PREVIEW_EMAIL] LINE 364: Calling datetime.now().date()")
                current_date = datetime.now().date()
                print(f"[PREVIEW_EMAIL] LINE 366: current_date (from now) = {current_date}")

            print("="*100)
            print("[PREVIEW_EMAIL] *** COMPARISON INFO ***")
            print(f"[PREVIEW_EMAIL] Comparing to BASELINE:")
            print(f"[PREVIEW_EMAIL]   - File: {baseline_snapshot['ace_export_filename']}")
            print(f"[PREVIEW_EMAIL]   - Baseline report_week_date: {baseline_week_date_str}")
            print(f"[PREVIEW_EMAIL]   - Baseline Date: {baseline_date}")
            print(f"[PREVIEW_EMAIL] Current report:")
            print(f"[PREVIEW_EMAIL]   - File: {session.get('current_file')}")
            print(f"[PREVIEW_EMAIL]   - Current report_week_date: {current_week_date_str}")
            print(f"[PREVIEW_EMAIL]   - Current Date: {current_date}")
            print(f"[PREVIEW_EMAIL] ABOUT TO CHECK: baseline_date == current_date")
            print(f"[PREVIEW_EMAIL] baseline_date value: {baseline_date}")
            print(f"[PREVIEW_EMAIL] current_date value: {current_date}")
            print(f"[PREVIEW_EMAIL] baseline_date type: {type(baseline_date)}")
            print(f"[PREVIEW_EMAIL] current_date type: {type(current_date)}")
            comparison_result = (baseline_date == current_date)
            print(f"[PREVIEW_EMAIL] COMPARISON RESULT: baseline_date == current_date = {comparison_result}")
            print(f"[PREVIEW_EMAIL] Same day? {comparison_result}")
            print("="*100)

            print(f"[PREVIEW_EMAIL] LINE 391: About to check if baseline_date == current_date")
            print(f"[PREVIEW_EMAIL] LINE 392: comparison_result = {comparison_result}")
            if baseline_date == current_date:
                print("[PREVIEW_EMAIL] ⚠️ Skipping comparison - same day reports")
                print(f"[PREVIEW_EMAIL] ❌ Setting comparison_data = None")
                print(f"[PREVIEW_EMAIL] ❌ Setting previous_stats = None")
                comparison_data = None
                previous_stats = None
                print(f"[PREVIEW_EMAIL] comparison_data is now: {comparison_data}")
                print(f"[PREVIEW_EMAIL] previous_stats is now: {previous_stats}")
            else:
                print("[PREVIEW_EMAIL] Step 4: ✅ Different days - comparison WILL run")
                print("[PREVIEW_EMAIL] Step 4: Calling db.compare_snapshots()...")
                print(f"[PREVIEW_EMAIL] Step 4: - df_all has {len(df_all)} rows")
                print(f"[PREVIEW_EMAIL] Step 4: - baseline snapshot ID: {baseline_snapshot['snapshot_id']}")

                comparison_data = db.compare_snapshots(df_all, baseline_snapshot['snapshot_id'])

                print(f"[PREVIEW_EMAIL] Step 4: db.compare_snapshots() RETURNED")
                print(f"[PREVIEW_EMAIL] Step 4: comparison_data TYPE: {type(comparison_data)}")
                print(f"[PREVIEW_EMAIL] Step 4: comparison_data IS NONE: {comparison_data is None}")
                if comparison_data:
                    print(f"[PREVIEW_EMAIL] Step 4: comparison_data KEYS: {list(comparison_data.keys())}")
                    print(f"[PREVIEW_EMAIL] Step 4: - new_ops: {len(comparison_data.get('new_ops', []))} items")
                    print(f"[PREVIEW_EMAIL] Step 4: - closed_ops: {len(comparison_data.get('closed_ops', []))} items")
                    print(f"[PREVIEW_EMAIL] Step 4: - status_changes: {len(comparison_data.get('status_changes', []))} items")

                previous_stats = baseline_snapshot
                print(f"[PREVIEW_EMAIL] Step 4: previous_stats TYPE: {type(previous_stats)}")
                print(f"[PREVIEW_EMAIL] Step 4: previous_stats IS NONE: {previous_stats is None}")
                if previous_stats:
                    print(f"[PREVIEW_EMAIL] Step 4: previous_stats KEYS: {list(previous_stats.keys())}")

                print(f"[PREVIEW_EMAIL] Step 4 DONE: Comparison complete")

        # Generate HTML
        print("[PREVIEW_EMAIL] Step 5: Preparing stats...")
        current_stats = session['stats']
        print("=" * 100)
        print("[PREVIEW_EMAIL] *** CURRENT STATS FROM SESSION ***")
        print(f"[PREVIEW_EMAIL] Stats keys: {list(current_stats.keys())}")
        print(f"[PREVIEW_EMAIL] Full stats dict: {current_stats}")
        print(f"[PREVIEW_EMAIL] WA count: {current_stats.get('well_architected_count', 'KEY NOT FOUND')}")
        print(f"[PREVIEW_EMAIL] RAPID count: {current_stats.get('rapid_pilot_count', 'KEY NOT FOUND')}")
        print("=" * 100)
        print(f"[PREVIEW_EMAIL] Step 5: Stats type check - processed_date is {type(current_stats['processed_date'])}")

        # Convert processed_date string to datetime if it's a string
        if isinstance(current_stats['processed_date'], str):
            print("[PREVIEW_EMAIL] Step 5: Converting processed_date from string to datetime")
            current_stats['processed_date'] = datetime.fromisoformat(current_stats['processed_date'])
        print(f"[PREVIEW_EMAIL] Step 5 DONE: Stats ready")

        print("[PREVIEW_EMAIL] Step 6: Generating email HTML...")
        print("=" * 100)
        print("[PREVIEW_EMAIL] *** ABOUT TO CALL generate_email_html() ***")
        print(f"[PREVIEW_EMAIL] Passing previous_stats: {previous_stats is not None}")
        if previous_stats:
            print(f"[PREVIEW_EMAIL] previous_stats TYPE: {type(previous_stats)}")
            print(f"[PREVIEW_EMAIL] previous_stats KEYS: {list(previous_stats.keys()) if isinstance(previous_stats, dict) else 'NOT A DICT'}")
            print(f"[PREVIEW_EMAIL] previous_stats CONTENT: {previous_stats}")
        else:
            print(f"[PREVIEW_EMAIL] ❌ previous_stats is NULL/NONE - NO COMPARISON WILL SHOW!")

        print(f"\n[PREVIEW_EMAIL] Passing comparison_data: {comparison_data is not None}")
        if comparison_data:
            print(f"[PREVIEW_EMAIL] comparison_data TYPE: {type(comparison_data)}")
            print(f"[PREVIEW_EMAIL] comparison_data KEYS: {list(comparison_data.keys()) if isinstance(comparison_data, dict) else 'NOT A DICT'}")
            if isinstance(comparison_data, dict):
                new_count = len(comparison_data.get('new_ops', []))
                closed_count = len(comparison_data.get('closed_ops', []))
                changes_count = len(comparison_data.get('status_changes', []))
                print(f"[PREVIEW_EMAIL] comparison_data NEW OPS: {new_count}")
                print(f"[PREVIEW_EMAIL] comparison_data CLOSED OPS: {closed_count}")
                print(f"[PREVIEW_EMAIL] comparison_data STATUS CHANGES: {changes_count}")
        else:
            print(f"[PREVIEW_EMAIL] ❌ comparison_data is NULL/NONE - NO COMPARISON WILL SHOW!")
        print("=" * 100)

        email_html = generate_email_html(df_stale, df_open, current_stats, previous_stats, comparison_data)
        print(f"[PREVIEW_EMAIL] Step 6 DONE: Generated {len(email_html)} bytes of HTML")

        # SAVE HTML TO FILE (session cookies are too small for 11KB HTML!)
        print("[PREVIEW_EMAIL] Step 7: Saving HTML to file...")
        html_filename = f"email_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        html_path = os.path.join(app.config['TEMP_EMAIL_FOLDER'], html_filename)
        print(f"[PREVIEW_EMAIL] Step 7: Writing to {html_path}")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(email_html)
        print(f"[PREVIEW_EMAIL] Step 7: File written successfully")

        session['email_html_file'] = html_filename
        print(f"[PREVIEW_EMAIL] Step 7 DONE: Saved to session as '{html_filename}'")

        print("[PREVIEW_EMAIL] Step 8: Rendering template...")
        stale_count = len(df_stale[~df_stale['Opportunity id'].isin(EXCLUDED_OPS)])
        print(f"[PREVIEW_EMAIL] Step 8: Stale count (excluding excluded ops): {stale_count}")

        result = render_template('email_preview.html',
                             email_html=email_html,
                             stale_count=stale_count)
        print("[PREVIEW_EMAIL] Step 8 DONE: Template rendered")
        print("[PREVIEW_EMAIL] ✅ SUCCESS - Preview complete")
        print("="*80 + "\n")
        return result

    except Exception as e:
        print(f"[PREVIEW_EMAIL] ❌ EXCEPTION at some step: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"[PREVIEW_EMAIL] FULL TRACEBACK:\n{traceback.format_exc()}")
        print("="*80 + "\n")
        return f"Error generating preview: {str(e)}", 500


@app.route('/send_test_email', methods=['POST'])
def send_test_email():
    """Send test email to user only - JUST SEND THE ALREADY GENERATED HTML!"""
    print("\n" + "="*80)
    print("[SEND_TEST_EMAIL] STARTING")
    print("="*80)
    print("[SEND_TEST_EMAIL] Route called")
    print(f"[SEND_TEST_EMAIL] Request method: {request.method}")
    print(f"[SEND_TEST_EMAIL] Request content type: {request.content_type}")

    data = request.get_json()
    print(f"[SEND_TEST_EMAIL] Got data type: {type(data)}")
    print(f"[SEND_TEST_EMAIL] Data keys: {list(data.keys()) if data else 'None'}")

    password = data.get('password') if data else None
    print(f"[SEND_TEST_EMAIL] Password received: {bool(password)}")

    if not password:
        print("[SEND_TEST_EMAIL] ERROR: No password provided")
        print("="*80 + "\n")
        return jsonify({'success': False, 'error': 'Password required'}), 400

    # ULTRA DETAILED PASSWORD ANALYSIS
    print(f"\n[SEND_TEST_EMAIL] ========== PASSWORD ANALYSIS ==========")
    print(f"[SEND_TEST_EMAIL] Password type: {type(password)}")
    print(f"[SEND_TEST_EMAIL] Password length: {len(password)}")
    print(f"[SEND_TEST_EMAIL] Password repr: {repr(password)}")
    print(f"[SEND_TEST_EMAIL] Password first 4 chars: {repr(password[:4])}")
    print(f"[SEND_TEST_EMAIL] Password last 4 chars: {repr(password[-4:])}")

    print(f"[SEND_TEST_EMAIL] Character-by-character analysis:")
    for i, char in enumerate(password):
        char_code = ord(char)
        is_ascii = char_code < 128
        is_space = char.isspace()
        char_name = 'SPACE' if is_space else 'NON-BREAKING-SPACE' if char_code == 160 else 'REGULAR'
        print(f"[SEND_TEST_EMAIL]   [{i:2d}] {repr(char):8s} ord={char_code:3d} ASCII={is_ascii} {char_name}")

    print(f"[SEND_TEST_EMAIL] Password will be cleaned by send_email() function")
    print(f"[SEND_TEST_EMAIL] ==========================================\n")

    print(f"[SEND_TEST_EMAIL] Checking session for email_html_file...")
    print(f"[SEND_TEST_EMAIL] Session keys: {list(session.keys())}")

    if 'email_html_file' not in session:
        print("[SEND_TEST_EMAIL] ERROR: No email HTML file in session - preview first!")
        print("="*80 + "\n")
        return jsonify({'success': False, 'error': 'Please preview email first'}), 400

    try:
        # Read the ALREADY GENERATED HTML from file
        html_filename = session['email_html_file']
        print(f"[SEND_TEST_EMAIL] HTML filename from session: {html_filename}")

        html_path = os.path.join(app.config['TEMP_EMAIL_FOLDER'], html_filename)
        print(f"[SEND_TEST_EMAIL] Full HTML path: {html_path}")
        print(f"[SEND_TEST_EMAIL] File exists: {os.path.exists(html_path)}")

        print(f"[SEND_TEST_EMAIL] Opening file for reading...")
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        print(f"[SEND_TEST_EMAIL] File read successfully - {len(html_content)} bytes")
        print(f"[SEND_TEST_EMAIL] First 100 chars: {html_content[:100]}")

        # Create simple email message with the HTML
        print(f"[SEND_TEST_EMAIL] Importing email modules...")
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        print(f"[SEND_TEST_EMAIL] Email modules imported")

        print(f"[SEND_TEST_EMAIL] Creating MIMEMultipart message...")
        msg = MIMEMultipart('alternative')
        print(f"[SEND_TEST_EMAIL] MIMEMultipart created")

        msg['Subject'] = 'ACE Hygiene - TEST'
        print(f"[SEND_TEST_EMAIL] Subject set: {msg['Subject']}")

        msg['From'] = 'Gianluca Formica <gianluca.formica@colibridigital.io>'
        print(f"[SEND_TEST_EMAIL] From set: {msg['From']}")

        msg['To'] = 'gianluca.formica@colibridigital.io'
        print(f"[SEND_TEST_EMAIL] To set: {msg['To']}")

        print(f"[SEND_TEST_EMAIL] Creating HTML MIMEText part...")
        html_part = MIMEText(html_content, 'html', 'utf-8')
        print(f"[SEND_TEST_EMAIL] HTML MIMEText created")

        print(f"[SEND_TEST_EMAIL] Attaching HTML to message...")
        msg.attach(html_part)
        print(f"[SEND_TEST_EMAIL] HTML attached - total message size: {len(msg.as_string())} bytes")

        # SEND IT!
        print("[SEND_TEST_EMAIL] Calling send_email function...")
        success, message = send_email(msg, password)
        print(f"[SEND_TEST_EMAIL] send_email returned: success={success}, message={message}")

        print(f"[SEND_TEST_EMAIL] Creating response...")
        response = jsonify({'success': success, 'message': message})
        print(f"[SEND_TEST_EMAIL] ✅ SUCCESS - Returning response")
        print("="*80 + "\n")
        return response

    except Exception as e:
        print(f"[SEND_TEST_EMAIL] ❌ EXCEPTION: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"[SEND_TEST_EMAIL] FULL TRACEBACK:\n{traceback.format_exc()}")
        print("="*80 + "\n")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/send_email', methods=['POST'])
def send_email_route():
    """Send email to all recipients and save snapshot - USE SAVED HTML!"""
    print("\n" + "="*80)
    print("[SEND EMAIL] ========== STARTING SEND TO ALL RECIPIENTS ==========")
    print("="*80)
    print(f"[SEND EMAIL] Request method: {request.method}")
    print(f"[SEND EMAIL] Request content type: {request.content_type}")

    data = request.get_json()
    print(f"[SEND EMAIL] Got data type: {type(data)}")
    print(f"[SEND EMAIL] Data keys: {list(data.keys()) if data else 'None'}")

    password = data.get('password') if data else None
    print(f"[SEND EMAIL] Password received: {bool(password)}")

    if not password:
        print("[SEND EMAIL] ❌ ERROR: No password")
        print("="*80 + "\n")
        return jsonify({'success': False, 'error': 'Password required'}), 400

    # ULTRA DETAILED PASSWORD ANALYSIS
    print(f"\n[SEND EMAIL] ========== PASSWORD ANALYSIS ==========")
    print(f"[SEND EMAIL] Password type: {type(password)}")
    print(f"[SEND EMAIL] Password length: {len(password)}")
    print(f"[SEND EMAIL] Password repr: {repr(password)}")

    print(f"[SEND EMAIL] Character-by-character analysis:")
    for i, char in enumerate(password):
        char_code = ord(char)
        is_ascii = char_code < 128
        is_space = char.isspace()
        char_name = 'SPACE' if is_space else 'NON-BREAKING-SPACE' if char_code == 160 else 'REGULAR'
        print(f"[SEND EMAIL]   [{i:2d}] {repr(char):8s} ord={char_code:3d} ASCII={is_ascii} {char_name}")

    print(f"[SEND EMAIL] Password will be cleaned by send_email() function")
    print(f"[SEND EMAIL] ==========================================\n")

    print(f"[SEND EMAIL] Checking session...")
    print(f"[SEND EMAIL] Session keys: {list(session.keys())}")

    if 'email_html_file' not in session:
        print("[SEND EMAIL] ❌ ERROR: No email HTML file in session")
        print("="*80 + "\n")
        return jsonify({'success': False, 'error': 'Please preview email first'}), 400

    if 'current_file' not in session:
        print("[SEND EMAIL] ❌ ERROR: No current file")
        print("="*80 + "\n")
        return jsonify({'success': False, 'error': 'No report generated'}), 400

    print(f"[SEND EMAIL] ✓ Session valid")

    try:
        # Read the ALREADY GENERATED HTML from file
        html_filename = session['email_html_file']
        html_path = os.path.join(app.config['TEMP_EMAIL_FOLDER'], html_filename)

        print(f"[SEND EMAIL] Reading HTML from {html_path}")
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Create email message with saved HTML
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email_config import EMAIL_CONFIG

        # Generate dynamic subject with current date
        current_date = datetime.now().strftime('%d %b %Y')
        subject = f"ACE Hygiene Report - {current_date}"

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{EMAIL_CONFIG['from_name']} <{EMAIL_CONFIG['from_email']}>"
        msg['To'] = ', '.join(EMAIL_CONFIG['to'])
        if EMAIL_CONFIG['cc']:
            msg['Cc'] = ', '.join(EMAIL_CONFIG['cc'])

        print(f"[SEND EMAIL] TO: {msg['To']}")
        print(f"[SEND EMAIL] CC: {msg.get('Cc', 'None')}")
        print(f"[SEND EMAIL] Attaching HTML ({len(html_content)} chars)")

        msg.attach(MIMEText(html_content, 'html'))

        # SEND IT!
        print("[SEND EMAIL] Calling send_email...")
        success, message = send_email(msg, password)

        if success:
            print("[SEND EMAIL] Email sent successfully, saving snapshot...")

            # NOW reload data to save snapshot
            result = process_ace_file(session['current_file'])
            df_all = result['df_all']

            # Get report week date from session
            report_week_date = session.get('report_week_date')
            log(f"[SEND_EMAIL] *** REPORT WEEK DATE FROM SESSION: {report_week_date} ***")

            # Save snapshot to database
            snapshot_id = db.save_snapshot(
                df_all=df_all,
                snapshot_date=datetime.now(),
                ace_filename=session['current_filename'],
                ace_file_date=result['stats']['file_date'],
                email_recipients=EMAIL_CONFIG['to'] + EMAIL_CONFIG['cc'],
                report_week_date=report_week_date,
                notes=f"Weekly report sent - {session['stats']['stale_ops_count']} stale ops"
            )

            print(f"[SEND EMAIL] Snapshot {snapshot_id} saved!")
            return jsonify({
                'success': True,
                'message': f'{message} Snapshot saved (ID: {snapshot_id})'
            })
        else:
            print(f"[SEND EMAIL] Email failed: {message}")
            return jsonify({'success': False, 'error': message}), 500

    except Exception as e:
        print(f"[SEND EMAIL] EXCEPTION: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/history')
def history():
    """View historical snapshots."""
    snapshots = db.get_all_snapshots()
    return render_template('history.html', snapshots=snapshots)


@app.route('/validation_errors')
def validation_errors():
    """View detailed validation errors from the last validation."""
    if 'validation_results' not in session:
        return "No validation results available. Please upload a weekly file first.", 400

    validation_results = session['validation_results']
    return render_template('validation_errors.html',
                         validation_results=validation_results)


@app.route('/send_basic_test_email', methods=['POST'])
def send_basic_test_email():
    """Send the most basic test email possible - ULTRA DETAILED LOGGING."""
    print("\n" + "="*100)
    print("[BASIC TEST EMAIL] ========== STARTING BASIC EMAIL TEST ==========")
    print("="*100)

    # STEP 1: GET REQUEST DATA
    print("\n[STEP 1] Getting request data...")
    print(f"[STEP 1] Request method: {request.method}")
    print(f"[STEP 1] Request content type: {request.content_type}")

    data = request.get_json()
    print(f"[STEP 1] Got JSON data: {type(data)}")
    print(f"[STEP 1] Data keys: {list(data.keys()) if data else 'None'}")

    password = data.get('password') if data else None
    print(f"[STEP 1] Password extracted: {'YES' if password else 'NO'}")

    if not password:
        print("[STEP 1] ❌ FAIL: No password provided")
        return jsonify({'success': False, 'error': 'Password required'}), 400

    # STEP 2: ANALYZE PASSWORD IN DETAIL
    print("\n[STEP 2] Analyzing password in EXTREME detail...")
    print(f"[STEP 2] Password type: {type(password)}")
    print(f"[STEP 2] Password length: {len(password)} characters")
    print(f"[STEP 2] Password first 4 chars: '{password[:4]}'")
    print(f"[STEP 2] Password last 4 chars: '{password[-4:]}'")
    print(f"[STEP 2] Password repr: {repr(password)}")

    # Check each character
    print(f"[STEP 2] Checking each character:")
    for i, char in enumerate(password):
        char_code = ord(char)
        char_repr = repr(char)
        is_ascii = char_code < 128
        print(f"[STEP 2]   Char {i}: {char_repr} (ord={char_code}, ASCII={is_ascii})")

    # CLEAN the password - remove ALL non-ASCII characters
    print(f"\n[STEP 2] CLEANING password - removing non-ASCII characters...")
    original_password = password
    password = ''.join(char for char in password if ord(char) < 128 and not char.isspace())
    print(f"[STEP 2] Original password: {repr(original_password)}")
    print(f"[STEP 2] Cleaned password: {repr(password)}")
    print(f"[STEP 2] Length before: {len(original_password)}, after: {len(password)}")

    if len(password) != 16:
        print(f"[STEP 2] ⚠️ WARNING: Gmail App Passwords are 16 characters, got {len(password)}")

    try:
        # STEP 3: IMPORT LIBRARIES
        print("\n[STEP 3] Importing email libraries...")
        from email.mime.text import MIMEText
        import smtplib
        print("[STEP 3] ✓ Imports successful")

        # STEP 4: SET EMAIL ADDRESS
        print("\n[STEP 4] Setting up email address...")
        email = 'gianluca.formica@colibridigital.io'
        print(f"[STEP 4] Email address: {email}")
        print(f"[STEP 4] Email type: {type(email)}")
        print(f"[STEP 4] Email repr: {repr(email)}")

        # STEP 5: CREATE MESSAGE
        print("\n[STEP 5] Creating email message...")
        print("[STEP 5] Creating MIMEText with UTF-8 encoding...")
        msg = MIMEText('TEST', 'plain', 'utf-8')
        print("[STEP 5] ✓ MIMEText created")

        print("[STEP 5] Setting message headers...")
        msg['Subject'] = 'TEST'
        print(f"[STEP 5]   Subject set: {msg['Subject']}")
        msg['From'] = email
        print(f"[STEP 5]   From set: {msg['From']}")
        msg['To'] = email
        print(f"[STEP 5]   To set: {msg['To']}")

        # STEP 6: CONNECT TO SMTP
        print("\n[STEP 6] Connecting to Gmail SMTP server...")
        print("[STEP 6] Server: smtp.gmail.com")
        print("[STEP 6] Port: 587")
        print("[STEP 6] Creating SMTP connection...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        print("[STEP 6] ✓ SMTP object created")

        print("[STEP 6] Setting debug level to 2 (full SMTP protocol logging)...")
        server.set_debuglevel(2)
        print("[STEP 6] ✓ Debug level set")

        # STEP 7: START TLS
        print("\n[STEP 7] Starting TLS encryption...")
        tls_response = server.starttls()
        print(f"[STEP 7] TLS response: {tls_response}")
        print("[STEP 7] ✓ TLS encryption started")

        # STEP 8: LOGIN (CRITICAL STEP)
        print("\n[STEP 8] ========== ATTEMPTING LOGIN (CRITICAL) ==========")
        print(f"[STEP 8] Username: {email}")
        print(f"[STEP 8] Username type: {type(email)}")
        print(f"[STEP 8] Username repr: {repr(email)}")
        print(f"[STEP 8] Password type: {type(password)}")
        print(f"[STEP 8] Password length: {len(password)}")
        print(f"[STEP 8] Password repr: {repr(password)}")
        print(f"[STEP 8] Password is ASCII-only: {all(ord(c) < 128 for c in password)}")

        print("[STEP 8] Calling server.login()...")
        server.login(email, password)
        print("[STEP 8] ✓✓✓ LOGIN SUCCESSFUL! ✓✓✓")

        # STEP 9: SEND MESSAGE
        print("\n[STEP 9] Sending email message...")
        print("[STEP 9] Calling server.send_message()...")
        send_response = server.send_message(msg)
        print(f"[STEP 9] Send response: {send_response}")
        print("[STEP 9] ✓ Message sent!")

        # STEP 10: CLOSE CONNECTION
        print("\n[STEP 10] Closing SMTP connection...")
        server.quit()
        print("[STEP 10] ✓ Connection closed")

        # SUCCESS!
        print("\n" + "="*100)
        print("[SUCCESS] ✅✅✅ BASIC TEST EMAIL SENT SUCCESSFULLY! ✅✅✅")
        print("="*100 + "\n")

        return jsonify({
            'success': True,
            'message': 'Test email sent successfully! Check your inbox.'
        })

    except smtplib.SMTPAuthenticationError as e:
        print("\n" + "="*100)
        print("[ERROR] ❌❌❌ SMTP AUTHENTICATION ERROR ❌❌❌")
        print("="*100)
        print(f"[ERROR] Error type: SMTPAuthenticationError")
        print(f"[ERROR] Error message: {str(e)}")
        print(f"[ERROR] Error repr: {repr(e)}")

        import traceback
        print(f"[ERROR] Full traceback:")
        print(traceback.format_exc())

        error_msg = f"Gmail authentication failed: {str(e)}"
        return jsonify({
            'success': False,
            'error': f'{error_msg}\n\nPlease verify:\n1. You generated an App Password at https://myaccount.google.com/apppasswords\n2. 2-Step Verification is enabled\n3. You copied the 16-character password correctly (no spaces)'
        }), 500

    except Exception as e:
        print("\n" + "="*100)
        print("[ERROR] ❌❌❌ UNEXPECTED ERROR ❌❌❌")
        print("="*100)
        print(f"[ERROR] Error type: {type(e).__name__}")
        print(f"[ERROR] Error message: {str(e)}")
        print(f"[ERROR] Error repr: {repr(e)}")

        import traceback
        print(f"[ERROR] Full traceback:")
        print(traceback.format_exc())
        print("="*100 + "\n")

        return jsonify({'success': False, 'error': f'{type(e).__name__}: {str(e)}'}), 500


@app.route('/get_distribution_list')
def get_distribution_list():
    """Get current email distribution list."""
    from email_config import EMAIL_CONFIG

    return jsonify({
        'success': True,
        'to': EMAIL_CONFIG['to'],
        'cc': EMAIL_CONFIG['cc']
    })


@app.route('/update_distribution_list', methods=['POST'])
def update_distribution_list():
    """Update email distribution list in email_config.py."""
    data = request.get_json()

    if not data or 'to' not in data or 'cc' not in data:
        return jsonify({'success': False, 'error': 'Invalid data'}), 400

    to_emails = data.get('to', [])
    cc_emails = data.get('cc', [])

    # Validate emails
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    for email in to_emails + cc_emails:
        if not re.match(email_pattern, email):
            return jsonify({
                'success': False,
                'error': f'Invalid email address: {email}'
            }), 400

    try:
        # Read current email_config.py
        config_path = 'email_config.py'
        with open(config_path, 'r') as f:
            lines = f.readlines()

        # Build new file content
        new_lines = []
        in_to_section = False
        in_cc_section = False
        in_email_config = False

        i = 0
        while i < len(lines):
            line = lines[i]

            # Start of EMAIL_CONFIG dict
            if 'EMAIL_CONFIG = {' in line:
                in_email_config = True
                new_lines.append(line)
                i += 1
                continue

            # End of EMAIL_CONFIG dict
            if in_email_config and line.strip() == '}':
                in_email_config = False
                new_lines.append(line)
                i += 1
                continue

            # Inside EMAIL_CONFIG, look for 'to' or 'cc'
            if in_email_config:
                if "'to':" in line or '"to":' in line:
                    in_to_section = True
                    new_lines.append("    'to': [\n")
                    for email in to_emails:
                        new_lines.append(f"        '{email}',\n")
                    new_lines.append("    ],\n")

                    # Skip until closing bracket
                    i += 1
                    while i < len(lines) and ']' not in lines[i]:
                        i += 1
                    i += 1  # Skip the closing bracket line
                    continue

                elif "'cc':" in line or '"cc":' in line:
                    in_cc_section = True
                    new_lines.append("    'cc': [\n")
                    for email in cc_emails:
                        new_lines.append(f"        '{email}',\n")
                    new_lines.append("    ],\n")

                    # Skip until closing bracket
                    i += 1
                    while i < len(lines) and ']' not in lines[i]:
                        i += 1
                    i += 1  # Skip the closing bracket line
                    continue

            new_lines.append(line)
            i += 1

        # Write updated config
        with open(config_path, 'w') as f:
            f.writelines(new_lines)

        # Reload the module to get updated values
        import importlib
        import email_config
        importlib.reload(email_config)

        print(f"[CONFIG] Distribution list updated: {len(to_emails)} TO, {len(cc_emails)} CC")

        return jsonify({
            'success': True,
            'message': f'Distribution list updated! {len(to_emails)} TO, {len(cc_emails)} CC'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/save_report', methods=['POST'])
def save_report():
    """Save the weekly report to database WITHOUT sending email"""
    print("\n" + "🔥🔥🔥" * 30)
    print("[SAVE_REPORT] ==================== ROUTE ENTERED ====================")
    print("[SAVE_REPORT] Time:", datetime.now().isoformat())
    print("🔥🔥🔥" * 30 + "\n")

    log("[SAVE_REPORT] LINE 1049: Route called - saving report WITHOUT sending email")

    try:
        print("[SAVE_REPORT] LINE 1052: Starting try block")

        # Check if we have the required data in session
        print("[SAVE_REPORT] LINE 1055: Checking for 'current_file' in session")
        print(f"[SAVE_REPORT] LINE 1056: Session keys: {list(session.keys())}")

        if 'current_file' not in session:
            print("[SAVE_REPORT] LINE 1059: ERROR - No current_file in session!")
            return jsonify({'success': False, 'error': 'No report data in session. Please upload a weekly file first.'}), 400

        print("[SAVE_REPORT] LINE 1062: current_file FOUND in session")

        if 'stats' not in session:
            print("[SAVE_REPORT] LINE 1065: ERROR - No stats in session!")
            return jsonify({'success': False, 'error': 'No statistics in session. Please process a weekly file first.'}), 400

        print("[SAVE_REPORT] LINE 1068: stats FOUND in session")

        # Get data from session
        print("[SAVE_REPORT] LINE 1071: Getting data from session...")
        current_file = session['current_file']
        print(f"[SAVE_REPORT] LINE 1073: current_file = {current_file}")
        print(f"[SAVE_REPORT] LINE 1074: current_file type = {type(current_file)}")

        stats = session['stats']
        print(f"[SAVE_REPORT] LINE 1077: stats = {stats}")
        print(f"[SAVE_REPORT] LINE 1078: stats type = {type(stats)}")

        report_week_date = session.get('report_week_date')
        print(f"[SAVE_REPORT] LINE 1081: report_week_date = {report_week_date}")
        print(f"[SAVE_REPORT] LINE 1082: report_week_date type = {type(report_week_date)}")

        # DUPLICATE DETECTION: Check if snapshot with this report_week_date already exists
        print("[SAVE_REPORT] LINE 1084: CHECKING FOR DUPLICATE SNAPSHOT...")
        existing_snapshot = db.find_snapshot_by_week(report_week_date)
        print(f"[SAVE_REPORT] LINE 1086: existing_snapshot = {existing_snapshot}")

        if existing_snapshot:
            print(f"[SAVE_REPORT] LINE 1088: ⚠️ DUPLICATE FOUND! Snapshot ID {existing_snapshot['snapshot_id']}")
            log(f"[SAVE_REPORT] LINE 1089: Duplicate detected for week {report_week_date} - returning duplicate warning")
            return jsonify({
                'success': False,
                'duplicate': True,
                'existing_snapshot': existing_snapshot,
                'error': f"A report for week {report_week_date} already exists (Snapshot #{existing_snapshot['snapshot_id']}). Please confirm if you want to replace it."
            }), 409  # 409 Conflict status code

        print("[SAVE_REPORT] LINE 1099: No duplicate found - proceeding with save")

        log(f"[SAVE_REPORT] LINE 1084: Saving report for file: {current_file}")
        log(f"[SAVE_REPORT] LINE 1085: Report week date: {report_week_date}")
        log(f"[SAVE_REPORT] LINE 1086: Stats: {stats}")

        # Process the file again to get ALL the data we need
        print("[SAVE_REPORT] LINE 1089: Calling process_ace_file()")
        print(f"[SAVE_REPORT] LINE 1090: Passing file path: {current_file}")
        result = process_ace_file(current_file)
        print(f"[SAVE_REPORT] LINE 1092: process_ace_file() returned")
        print(f"[SAVE_REPORT] LINE 1093: result type = {type(result)}")
        print(f"[SAVE_REPORT] LINE 1094: result keys = {list(result.keys())}")

        df_all = result['df_all']
        print(f"[SAVE_REPORT] LINE 1097: df_all extracted")
        print(f"[SAVE_REPORT] LINE 1098: df_all type = {type(df_all)}")
        print(f"[SAVE_REPORT] LINE 1099: df_all shape = {df_all.shape}")
        print(f"[SAVE_REPORT] LINE 1100: df_all rows = {len(df_all)}")

        # CRITICAL FIX: Use save_snapshot NOT save_weekly_snapshot!
        print("[SAVE_REPORT] LINE 1103: About to call db.save_snapshot()")
        print(f"[SAVE_REPORT] LINE 1104: db object type = {type(db)}")
        print(f"[SAVE_REPORT] LINE 1105: db object = {db}")
        print(f"[SAVE_REPORT] LINE 1106: Checking if db has save_snapshot method...")
        print(f"[SAVE_REPORT] LINE 1107: hasattr(db, 'save_snapshot') = {hasattr(db, 'save_snapshot')}")
        print(f"[SAVE_REPORT] LINE 1108: dir(db) = {[m for m in dir(db) if not m.startswith('_')]}")

        print("[SAVE_REPORT] LINE 1110: Preparing arguments for save_snapshot()")
        ace_filename = os.path.basename(current_file)
        print(f"[SAVE_REPORT] LINE 1112: ace_filename = {ace_filename}")

        # Get file date from stats - IT'S A STRING, NEED TO PARSE IT!
        file_date_str = stats.get('processed_date')
        print(f"[SAVE_REPORT] LINE 1116: file_date_str from stats = {file_date_str}")
        print(f"[SAVE_REPORT] LINE 1117: file_date_str type = {type(file_date_str)}")

        # Parse the string to datetime object
        print("[SAVE_REPORT] LINE 1120: Parsing file_date_str to datetime object...")
        if file_date_str:
            file_date = datetime.fromisoformat(file_date_str)
            print(f"[SAVE_REPORT] LINE 1123: file_date parsed = {file_date}")
            print(f"[SAVE_REPORT] LINE 1124: file_date type = {type(file_date)}")
        else:
            file_date = datetime.now()
            print(f"[SAVE_REPORT] LINE 1127: file_date_str was None, using datetime.now() = {file_date}")

        snapshot_date = datetime.now()
        print(f"[SAVE_REPORT] LINE 1130: snapshot_date = {snapshot_date}")

        print("[SAVE_REPORT] LINE 1121: *** CALLING db.save_snapshot() ***")
        print(f"[SAVE_REPORT] LINE 1122: Arguments:")
        print(f"[SAVE_REPORT] LINE 1123:   df_all = DataFrame with {len(df_all)} rows")
        print(f"[SAVE_REPORT] LINE 1124:   snapshot_date = {snapshot_date}")
        print(f"[SAVE_REPORT] LINE 1125:   ace_filename = {ace_filename}")
        print(f"[SAVE_REPORT] LINE 1126:   ace_file_date = {file_date}")
        print(f"[SAVE_REPORT] LINE 1127:   report_week_date = {report_week_date}")

        snapshot_id = db.save_snapshot(
            df_all=df_all,
            snapshot_date=snapshot_date,
            ace_filename=ace_filename,
            ace_file_date=file_date,
            report_week_date=report_week_date
        )

        print(f"[SAVE_REPORT] LINE 1137: *** db.save_snapshot() RETURNED ***")
        print(f"[SAVE_REPORT] LINE 1138: snapshot_id = {snapshot_id}")
        print(f"[SAVE_REPORT] LINE 1139: snapshot_id type = {type(snapshot_id)}")

        log(f"[SAVE_REPORT] LINE 1141: ✅ Report saved successfully with snapshot_id: {snapshot_id}")

        # Mark in session that this report has been saved
        print("[SAVE_REPORT] LINE 1144: Marking report as saved in session")
        session['report_saved'] = True
        print(f"[SAVE_REPORT] LINE 1146: session['report_saved'] = {session['report_saved']}")

        session['saved_snapshot_id'] = snapshot_id
        print(f"[SAVE_REPORT] LINE 1149: session['saved_snapshot_id'] = {session['saved_snapshot_id']}")

        print("[SAVE_REPORT] LINE 1151: Creating success response")
        response = {
            'success': True,
            'message': f'Report saved successfully! Snapshot ID: {snapshot_id}',
            'snapshot_id': snapshot_id
        }
        print(f"[SAVE_REPORT] LINE 1157: response = {response}")

        print("[SAVE_REPORT] LINE 1159: ✅✅✅ SUCCESS - Returning response")
        print("🔥🔥🔥" * 30 + "\n")
        return jsonify(response)

    except Exception as e:
        print(f"[SAVE_REPORT] LINE 1164: ❌❌❌ EXCEPTION CAUGHT!")
        print(f"[SAVE_REPORT] LINE 1165: Exception type: {type(e).__name__}")
        print(f"[SAVE_REPORT] LINE 1166: Exception message: {str(e)}")
        import traceback
        print(f"[SAVE_REPORT] LINE 1168: Full traceback:")
        print(traceback.format_exc())
        log(f"[SAVE_REPORT] LINE 1170: ❌ Error: {str(e)}")
        print("🔥🔥🔥" * 30 + "\n")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/save_report_replace', methods=['POST'])
def save_report_replace():
    """Save report and REPLACE existing snapshot if duplicate exists"""
    log("[SAVE_REPORT_REPLACE] Route called - user confirmed replacement")

    try:
        # Get data from request
        data = request.get_json() or {}
        old_snapshot_id = data.get('old_snapshot_id')

        if not old_snapshot_id:
            return jsonify({'success': False, 'error': 'Missing old_snapshot_id'}), 400

        # Check session data
        if 'current_file' not in session or 'stats' not in session:
            return jsonify({'success': False, 'error': 'No report data in session'}), 400

        current_file = session['current_file']
        stats = session['stats']
        report_week_date = session.get('report_week_date')

        log(f"[SAVE_REPORT_REPLACE] Deleting old snapshot {old_snapshot_id}")
        # Delete the old snapshot FIRST
        db.delete_snapshot(old_snapshot_id)

        log(f"[SAVE_REPORT_REPLACE] Saving new snapshot for week {report_week_date}")
        # Now save the new one (same code as save_report)
        result = process_ace_file(current_file)
        df_all = result['df_all']

        file_date_str = stats.get('processed_date')
        if file_date_str:
            file_date = datetime.fromisoformat(file_date_str)
        else:
            file_date = datetime.now()

        snapshot_date = datetime.now()
        ace_filename = os.path.basename(current_file)

        snapshot_id = db.save_snapshot(
            df_all=df_all,
            snapshot_date=snapshot_date,
            ace_filename=ace_filename,
            ace_file_date=file_date,
            report_week_date=report_week_date
        )

        # Mark in session
        session['report_saved'] = True
        session['saved_snapshot_id'] = snapshot_id

        log(f"[SAVE_REPORT_REPLACE] ✅ Replaced snapshot {old_snapshot_id} with new snapshot {snapshot_id}")

        return jsonify({
            'success': True,
            'message': f'Report replaced successfully! Old snapshot deleted, new Snapshot ID: {snapshot_id}',
            'snapshot_id': snapshot_id,
            'replaced_snapshot_id': old_snapshot_id
        })

    except Exception as e:
        log(f"[SAVE_REPORT_REPLACE] ❌ Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/send_report_email', methods=['POST'])
def send_report_email():
    """Send the saved report via email - ONLY works after saving"""
    log("[SEND_EMAIL] Route called - attempting to send email")

    try:
        # CRITICAL: Check if report has been saved first
        if not session.get('report_saved', False):
            return jsonify({
                'success': False,
                'error': 'You must save the report first before sending! Click "Save Report" button.'
            }), 400

        # Check if we have required data
        if 'email_file' not in session:
            return jsonify({
                'success': False,
                'error': 'No email file found. Please preview the email first.'
            }), 400

        email_file = session['email_file']
        email_path = os.path.join(app.config['TEMP_EMAIL_FOLDER'], email_file)

        if not os.path.exists(email_path):
            return jsonify({
                'success': False,
                'error': f'Email file not found: {email_file}'
            }), 400

        log(f"[SEND_EMAIL] Reading email from: {email_path}")

        # Read the email HTML
        with open(email_path, 'r') as f:
            email_html = f.read()

        # Get email config
        from email_config import EMAIL_TO, EMAIL_CC

        log(f"[SEND_EMAIL] Sending to {len(EMAIL_TO)} TO recipients, {len(EMAIL_CC)} CC recipients")

        # Create and send email
        msg = create_email_message(
            subject="ACE Hygiene Report - Weekly Update",
            html_body=email_html,
            to_addresses=EMAIL_TO,
            cc_addresses=EMAIL_CC
        )

        # Get password from request
        data = request.get_json() or {}
        password = data.get('password', '')

        if not password:
            return jsonify({
                'success': False,
                'error': 'Gmail App Password is required to send email'
            }), 400

        send_email(msg, password)

        log(f"[SEND_EMAIL] ✅ Email sent successfully!")

        # Mark as sent in session
        session['email_sent'] = True

        return jsonify({
            'success': True,
            'message': f'Email sent successfully to {len(EMAIL_TO)} recipients!'
        })

    except Exception as e:
        log(f"[SEND_EMAIL] ❌ Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    print("=" * 80)
    print("ACE Report Hub - Starting...")
    print("=" * 80)
    print(f"Database: {'✓ Has baseline' if db.has_baseline() else '✗ No baseline yet'}")
    print(f"Excluded ops: {len(EXCLUDED_OPS)}")
    print("=" * 80)
    print("\nOpen your browser and navigate to:")
    print("  → http://localhost:5001")
    print("\nPress CTRL+C to stop the server")
    print("=" * 80)
    app.run(debug=True, port=5001)
