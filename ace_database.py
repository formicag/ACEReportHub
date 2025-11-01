#!/usr/bin/env python3
"""
Database module for ACE Report tracking
Stores weekly snapshots and opportunity history
"""

import sqlite3
import pandas as pd
from datetime import datetime
import json
import os


# Legacy ops to exclude from email reports but still track
EXCLUDED_OPS = [
    'O18244',
    'O38038',
    'O38001',
    'O37309',
    'O7015',
    'O7013',
    'O42819',
    'O1158289',
    # Additional legacy ops that need to be excluded
    'O6626478',
    'O6626601',
    'O6626677',
    'O6626721',
    'O8212897'
]


class ACEDatabase:
    """Manages SQLite database for ACE reports."""

    def __init__(self, db_path='ace_reports.db'):
        """Initialize database connection."""
        self.db_path = db_path
        self.create_tables()

    def connect(self):
        """Connect to database (creates new connection per request)."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # Access columns by name
        return conn

    def create_tables(self):
        """Create database tables if they don't exist."""
        conn = self.connect()
        cursor = conn.cursor()

        try:
            # Table 1: Weekly Snapshots metadata
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS weekly_snapshots (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_date TEXT NOT NULL,
                ace_export_filename TEXT NOT NULL,
                ace_export_date TEXT,
                total_all_ops INTEGER,
                total_open_ops INTEGER,
                total_reportable_ops INTEGER,
                total_excluded_ops INTEGER,
                avg_days_since_update REAL,
                stale_ops_count INTEGER,
                total_arr REAL,
                well_architected_count INTEGER DEFAULT 0,
                rapid_pilot_count INTEGER DEFAULT 0,
                new_ops_count INTEGER,
                closed_ops_count INTEGER,
                stage_changed_count INTEGER,
                consecutive_weeks_no_stale INTEGER DEFAULT 0,
                email_sent_to TEXT,
                notes TEXT,
                report_week_date TEXT
            )
            ''')

            # Table 2: Opportunities at each snapshot
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS opportunities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_id INTEGER NOT NULL,
                    opportunity_id TEXT NOT NULL,
                    customer_name TEXT,
                    status TEXT,
                    stage TEXT,
                    primary_contact_name TEXT,
                    date_created TEXT,
                    last_updated_date TEXT,
                    next_step TEXT,
                    target_close_date TEXT,
                    days_since_update INTEGER,
                    estimated_revenue REAL,
                    is_excluded BOOLEAN DEFAULT 0,
                    created_by TEXT,
                    aws_account_id TEXT,
                    FOREIGN KEY (snapshot_id) REFERENCES weekly_snapshots(snapshot_id)
                )
            ''')

            # Table 3: TEMPORARY SNAPSHOTS - Draft/Preview before email sent
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS temporary_snapshots (
                    temp_snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    report_week_date TEXT NOT NULL,
                    ace_export_filename TEXT NOT NULL,
                    ace_file_path TEXT NOT NULL,
                    total_all_ops INTEGER,
                    total_open_ops INTEGER,
                    total_reportable_ops INTEGER,
                    total_excluded_ops INTEGER,
                    avg_days_since_update REAL,
                    stale_ops_count INTEGER,
                    total_arr REAL,
                    well_architected_count INTEGER DEFAULT 0,
                    rapid_pilot_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'DRAFT',
                    promoted_to_snapshot_id INTEGER,
                    session_id TEXT,
                    FOREIGN KEY (promoted_to_snapshot_id) REFERENCES weekly_snapshots(snapshot_id)
                )
            ''')

            # Table 4: AUDIT LOG - Everything that happens
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_log (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_subtype TEXT,
                    snapshot_id INTEGER,
                    temp_snapshot_id INTEGER,
                    user_action TEXT,
                    source_file TEXT,
                    target_file TEXT,
                    report_week_date TEXT,
                    comparison_baseline_id INTEGER,
                    comparison_date_from TEXT,
                    comparison_date_to TEXT,
                    ops_count_before INTEGER,
                    ops_count_after INTEGER,
                    new_ops_count INTEGER,
                    closed_ops_count INTEGER,
                    status_changes_count INTEGER,
                    success BOOLEAN,
                    error_message TEXT,
                    metadata_json TEXT,
                    FOREIGN KEY (snapshot_id) REFERENCES weekly_snapshots(snapshot_id),
                    FOREIGN KEY (temp_snapshot_id) REFERENCES temporary_snapshots(temp_snapshot_id)
                )
            ''')

            # Table 5: DATA LINEAGE - Where did every piece of data come from?
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS data_lineage (
                    lineage_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    data_type TEXT NOT NULL,
                    snapshot_id INTEGER,
                    temp_snapshot_id INTEGER,
                    source_system TEXT NOT NULL,
                    source_file_path TEXT NOT NULL,
                    source_file_hash TEXT,
                    source_file_size INTEGER,
                    source_file_modified TEXT,
                    excel_sheet_name TEXT,
                    excel_row_count INTEGER,
                    user_provided_date TEXT,
                    system_detected_date TEXT,
                    date_source TEXT,
                    transformation_applied TEXT,
                    parent_lineage_id INTEGER,
                    metadata_json TEXT,
                    FOREIGN KEY (snapshot_id) REFERENCES weekly_snapshots(snapshot_id),
                    FOREIGN KEY (temp_snapshot_id) REFERENCES temporary_snapshots(temp_snapshot_id),
                    FOREIGN KEY (parent_lineage_id) REFERENCES data_lineage(lineage_id)
                )
            ''')

            # Table 6: SNAPSHOT METADATA - Extended info about each snapshot
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS snapshot_metadata (
                    metadata_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_id INTEGER NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT,
                    value_type TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (snapshot_id) REFERENCES weekly_snapshots(snapshot_id)
                )
            ''')

            # Index for faster queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_opportunity_id
                ON opportunities(opportunity_id)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_snapshot_id
                ON opportunities(snapshot_id)
            ''')

            # MIGRATIONS - Add columns if they don't exist
            cursor.execute("PRAGMA table_info(weekly_snapshots)")
            columns = [col[1] for col in cursor.fetchall()]

            if 'consecutive_weeks_no_stale' not in columns:
                print("[DB] Migrating: Adding consecutive_weeks_no_stale column")
                cursor.execute('''
                    ALTER TABLE weekly_snapshots
                    ADD COLUMN consecutive_weeks_no_stale INTEGER DEFAULT 0
                ''')
                conn.commit()
                print("[DB] Migration complete")

            if 'well_architected_count' not in columns:
                print("[DB] Migrating: Adding well_architected_count column")
                cursor.execute('''
                    ALTER TABLE weekly_snapshots
                    ADD COLUMN well_architected_count INTEGER DEFAULT 0
                ''')
                conn.commit()
                print("[DB] Migration complete")

            if 'rapid_pilot_count' not in columns:
                print("[DB] Migrating: Adding rapid_pilot_count column")
                cursor.execute('''
                    ALTER TABLE weekly_snapshots
                    ADD COLUMN rapid_pilot_count INTEGER DEFAULT 0
                ''')
                conn.commit()
                print("[DB] Migration complete")

            conn.commit()
            print("[DB] Database tables created/verified")
        finally:
            conn.close()

    def save_snapshot(self, df_all, snapshot_date, ace_filename, ace_file_date,
                     email_recipients=None, notes=None, report_week_date=None):
        """
        Save a weekly snapshot to the database.

        Args:
            df_all: DataFrame with ALL opportunities (not just open ones)
            snapshot_date: Datetime when snapshot was taken (sent email)
            ace_filename: Original ACE export filename
            ace_file_date: Date from the ACE export file
            email_recipients: List of email addresses sent to
            notes: Optional notes about this snapshot
            report_week_date: Manual date for the report week (YYYY-MM-DD string)

        Returns:
            snapshot_id of the saved snapshot
        """
        conn = self.connect()
        cursor = conn.cursor()

        # Define "open" ops for statistics (Status + Stage filtering)
        valid_statuses = ['Approved', 'In review', 'Draft', 'Submitted']
        valid_stages = ['Prospect', 'Qualified', 'Committed', 'Business Validation']

        df_open = df_all[
            df_all['Status'].isin(valid_statuses) &
            df_all['Stage'].isin(valid_stages)
        ].copy()

        # Calculate statistics for reportable (open, non-excluded) ops
        df_reportable = df_open[~df_open['Opportunity id'].isin(EXCLUDED_OPS)]
        df_excluded = df_open[df_open['Opportunity id'].isin(EXCLUDED_OPS)]

        # Calculate days since update for reportable ops
        df_with_days = df_reportable.copy()
        if 'days_since_update' not in df_with_days.columns:
            # Calculate if not already present
            df_with_days['days_since_update'] = df_with_days['Last Updated Date'].apply(
                self._calculate_days_since_update
            )

        avg_days = df_with_days['days_since_update'].mean() if len(df_with_days) > 0 else 0
        stale_count = len(df_with_days[df_with_days['days_since_update'] > 30])

        # Calculate ARR for open ops only
        arr_column = 'Estimated AWS Monthly Recurring Revenue'
        total_arr = df_open[arr_column].fillna(0).sum() if arr_column in df_open.columns else 0

        # Count Well-Architected opportunities (in OPEN ops only)
        wa_count = 0
        if 'APN Programs' in df_open.columns:
            wa_count = len(df_open[df_open['APN Programs'].fillna('').str.contains('Well-Architected', case=False, na=False)])
        print(f"[DB] Well-Architected count: {wa_count}")

        # Count RAPID PILOT opportunities (in OPEN ops only)
        rapid_count = 0
        if 'Partner Project Title' in df_open.columns:
            rapid_count = len(df_open[df_open['Partner Project Title'].fillna('').str.contains('RAPID PILOT', case=False, na=False)])
        print(f"[DB] RAPID PILOT count: {rapid_count}")

        # Calculate consecutive weeks with no stale ops
        consecutive_weeks_no_stale = 0
        if stale_count == 0:
            # Check last snapshot
            cursor.execute('''
                SELECT consecutive_weeks_no_stale, stale_ops_count
                FROM weekly_snapshots
                ORDER BY snapshot_id DESC
                LIMIT 1
            ''')
            last = cursor.fetchone()
            if last and last['stale_ops_count'] == 0:
                consecutive_weeks_no_stale = last['consecutive_weeks_no_stale'] + 1
            else:
                consecutive_weeks_no_stale = 1

        # Insert snapshot metadata
        cursor.execute('''
            INSERT INTO weekly_snapshots (
                snapshot_date, ace_export_filename, ace_export_date,
                total_all_ops, total_open_ops, total_reportable_ops, total_excluded_ops,
                avg_days_since_update, stale_ops_count, total_arr,
                well_architected_count, rapid_pilot_count,
                consecutive_weeks_no_stale,
                email_sent_to, notes, report_week_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            snapshot_date.isoformat(),
            ace_filename,
            ace_file_date.isoformat() if ace_file_date else None,
            len(df_all),  # ALL ops including closed
            len(df_open),  # Open ops only
            len(df_reportable),  # Open + not excluded
            len(df_excluded),  # Open + excluded
            avg_days,
            stale_count,
            total_arr,
            wa_count,  # SAVE Well-Architected count
            rapid_count,  # SAVE RAPID PILOT count
            consecutive_weeks_no_stale,
            json.dumps(email_recipients) if email_recipients else None,
            notes,
            report_week_date  # Manual report week date (YYYY-MM-DD)
        ))

        snapshot_id = cursor.lastrowid

        # Insert ALL opportunities for this snapshot (not just open ones)
        for _, row in df_all.iterrows():
            is_excluded = row['Opportunity id'] in EXCLUDED_OPS

            cursor.execute('''
                INSERT INTO opportunities (
                    snapshot_id, opportunity_id, customer_name, status, stage,
                    primary_contact_name, date_created, last_updated_date,
                    next_step, target_close_date, days_since_update,
                    estimated_revenue, is_excluded, created_by, aws_account_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                snapshot_id,
                row['Opportunity id'],
                row.get('Customer Company Name'),
                row.get('Status'),
                row.get('Stage'),
                row.get('Primary Contact Name'),
                str(row.get('Date Created')) if pd.notna(row.get('Date Created')) else None,
                str(row.get('Last Updated Date')) if pd.notna(row.get('Last Updated Date')) else None,
                row.get('Next Step'),
                str(row.get('Target Close Date')) if pd.notna(row.get('Target Close Date')) else None,
                row.get('days_since_update') if 'days_since_update' in row else None,
                row.get('Estimated AWS Monthly Recurring Revenue'),
                is_excluded,
                row.get('Created By'),
                str(row.get('AWS Account ID')) if pd.notna(row.get('AWS Account ID')) else None
            ))

        conn.commit()
        if consecutive_weeks_no_stale > 0:
            print(f"[DB] Saved snapshot {snapshot_id}: {len(df_all)} total ops, {len(df_open)} open ({len(df_reportable)} reportable, {len(df_excluded)} excluded), ARR: ${total_arr:,.2f}, WA: {wa_count}, RAPID: {rapid_count}, 🎉 {consecutive_weeks_no_stale} weeks with no stale ops!")
        else:
            print(f"[DB] Saved snapshot {snapshot_id}: {len(df_all)} total ops, {len(df_open)} open ({len(df_reportable)} reportable, {len(df_excluded)} excluded), ARR: ${total_arr:,.2f}, WA: {wa_count}, RAPID: {rapid_count}")
        conn.close()

        return snapshot_id

    def get_last_snapshot(self):
        """Get the most recent snapshot metadata."""
        conn = self.connect()
        try:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM weekly_snapshots
                ORDER BY snapshot_id DESC
                LIMIT 1
            ''')

            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_baseline_snapshot(self):
        """Get the FIRST/BASELINE snapshot (for week-over-week comparison)."""
        conn = self.connect()
        try:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM weekly_snapshots
                ORDER BY snapshot_id ASC
                LIMIT 1
            ''')

            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_snapshot_opportunities(self, snapshot_id):
        """Get all opportunities from a specific snapshot as DataFrame."""
        conn = self.connect()
        try:
            query = '''
                SELECT * FROM opportunities
                WHERE snapshot_id = ?
            '''

            df = pd.read_sql_query(query, conn, params=(snapshot_id,))
            print(f"[DB] Retrieved {len(df)} opportunities from snapshot {snapshot_id}")
            return df
        finally:
            conn.close()

    def compare_snapshots(self, current_df, previous_snapshot_id):
        """
        Compare current opportunities with previous snapshot.

        Compares ALL ops to detect stage changes, but filters results:
        - new_ops: Only NEW ops that are currently OPEN
        - closed_ops: Ops that were OPEN last week and are now closed/launched/not open
        - status_changes: Stage changes for ops in both snapshots

        Returns:
            dict with keys: new_ops, closed_ops, status_changes
        """
        # Get previous snapshot (ALL ops)
        prev_df = self.get_snapshot_opportunities(previous_snapshot_id)

        # Define "open" criteria
        valid_statuses = ['Approved', 'In review', 'Draft', 'Submitted']
        valid_stages = ['Prospect', 'Qualified', 'Committed', 'Business Validation']

        # Filter for open ops in both snapshots
        current_open = current_df[
            current_df['Status'].isin(valid_statuses) &
            current_df['Stage'].isin(valid_stages)
        ]

        prev_open = prev_df[
            prev_df['status'].isin(valid_statuses) &
            prev_df['stage'].isin(valid_stages)
        ]

        current_ops = set(current_df['Opportunity id'])
        prev_ops = set(prev_df['opportunity_id'])

        current_open_ids = set(current_open['Opportunity id'])
        prev_open_ids = set(prev_open['opportunity_id'])

        # NEW OPS: ops that are in current ALL but not in previous ALL, AND are currently open
        new_op_ids = (current_ops - prev_ops) & current_open_ids
        new_ops = current_df[current_df['Opportunity id'].isin(new_op_ids)]

        # CLOSED OPS: ops that were OPEN last week but are NOT open this week
        # (either completely gone, or changed to Launched/Closed Lost)
        closed_op_ids = prev_open_ids - current_open_ids

        # Build closed_ops list with current stage information
        closed_ops_list = []
        for op_id in closed_op_ids:
            prev_row = prev_df[prev_df['opportunity_id'] == op_id].iloc[0]

            # Try to find current status
            if op_id in current_ops:
                curr_row = current_df[current_df['Opportunity id'] == op_id].iloc[0]
                current_stage = curr_row['Stage']
                current_status = curr_row['Status']
            else:
                current_stage = "Not in current report"
                current_status = "Not in current report"

            closed_ops_list.append({
                'opportunity_id': op_id,
                'customer_name': prev_row['customer_name'],
                'previous_stage': prev_row['stage'],
                'previous_status': prev_row['status'],
                'current_stage': current_stage,
                'current_status': current_status
            })

        # Find status/stage changes for ops that exist in BOTH snapshots (using ALL ops)
        common_ops = current_ops & prev_ops
        status_changes = []

        for op_id in common_ops:
            curr = current_df[current_df['Opportunity id'] == op_id].iloc[0]
            prev = prev_df[prev_df['opportunity_id'] == op_id].iloc[0]

            if curr['Stage'] != prev['stage'] or curr['Status'] != prev['status']:
                status_changes.append({
                    'opportunity_id': op_id,
                    'customer_name': curr['Customer Company Name'],
                    'old_status': prev['status'],
                    'new_status': curr['Status'],
                    'old_stage': prev['stage'],
                    'new_stage': curr['Stage'],
                    'created_by': curr.get('Created By', ''),
                    'estimated_revenue': curr.get('Estimated AWS Monthly Recurring Revenue', 0),
                    'close_reason': curr.get('Closed Reason', ''),
                    'last_updated_date': curr.get('Last Updated Date', ''),
                    'date_created': curr.get('Date Created', ''),
                    'partner_project_title': curr.get('Partner Project Title', ''),
                    'aws_account_id': curr.get('AWS Account ID', ''),
                    'aws_sales_rep_name': curr.get('AWS Sales Rep Name', '')
                })

        print(f"[DB] Comparison: {len(new_ops)} new OPEN ops, {len(closed_ops_list)} no longer open, {len(status_changes)} status changes")

        return {
            'new_ops': new_ops,
            'closed_ops': closed_ops_list,
            'status_changes': status_changes
        }

    def _calculate_days_since_update(self, last_updated_date):
        """Calculate days since last update from today."""
        if pd.isna(last_updated_date):
            return None

        # Try to parse date
        if isinstance(last_updated_date, datetime):
            parsed_date = last_updated_date
        else:
            date_formats = ["%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"]
            parsed_date = None
            for fmt in date_formats:
                try:
                    parsed_date = datetime.strptime(str(last_updated_date), fmt)
                    break
                except ValueError:
                    continue

            if parsed_date is None:
                try:
                    parsed_date = pd.to_datetime(last_updated_date)
                except:
                    return None

        today = datetime.now()
        delta = today - parsed_date
        return delta.days

    def get_all_snapshots(self):
        """Get list of all snapshots with ALL fields for display."""
        conn = self.connect()
        try:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT snapshot_id, snapshot_date, ace_export_filename,
                       total_open_ops, total_reportable_ops, stale_ops_count,
                       avg_days_since_update, total_arr,
                       well_architected_count, rapid_pilot_count,
                       consecutive_weeks_no_stale, report_week_date
                FROM weekly_snapshots
                ORDER BY snapshot_id DESC
            ''')

            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def has_baseline(self):
        """Check if database has at least one snapshot (baseline)."""
        conn = self.connect()
        try:
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) FROM weekly_snapshots')
            count = cursor.fetchone()[0]

            return count > 0
        finally:
            conn.close()

    def find_snapshot_by_week(self, report_week_date):
        """
        Find if a snapshot already exists for the given report week date.

        Args:
            report_week_date: The report week date to check (string in YYYY-MM-DD format)

        Returns:
            dict with snapshot info if found, None otherwise
        """
        conn = self.connect()
        try:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT snapshot_id, snapshot_date, ace_export_filename,
                       total_open_ops, total_reportable_ops, stale_ops_count,
                       report_week_date
                FROM weekly_snapshots
                WHERE report_week_date = ?
            ''', (report_week_date,))

            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    def delete_snapshot(self, snapshot_id):
        """
        Delete a snapshot and all its associated data.

        Args:
            snapshot_id: The ID of the snapshot to delete
        """
        conn = self.connect()
        try:
            cursor = conn.cursor()

            # Delete from opportunity_snapshots table first (foreign key)
            cursor.execute('DELETE FROM opportunity_snapshots WHERE snapshot_id = ?', (snapshot_id,))

            # Delete from weekly_snapshots table
            cursor.execute('DELETE FROM weekly_snapshots WHERE snapshot_id = ?', (snapshot_id,))

            conn.commit()
            print(f"[DB] Deleted snapshot {snapshot_id} and all associated opportunity records")
        finally:
            conn.close()
