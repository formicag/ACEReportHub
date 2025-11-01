#!/usr/bin/env python3
"""
COMPREHENSIVE AUDIT & DATA LINEAGE SYSTEM
Every action tracked. Every data source recorded. Full transparency.
"""

import sqlite3
import json
import hashlib
import os
from datetime import datetime


class AuditLogger:
    """
    The MOTHER OF ALL AUDIT TRAILS

    Tracks:
    - Every user action
    - Every file processed
    - Every comparison made
    - Every data transformation
    - Complete data lineage (where did this data come from?)
    - Full metadata about everything
    """

    def __init__(self, db_path):
        self.db_path = db_path

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def log_event(self, event_type, **kwargs):
        """
        Log EVERYTHING that happens in the system

        Args:
            event_type: Type of event (UPLOAD, COMPARISON, EMAIL_SENT, etc.)
            **kwargs: All the details about what happened
        """
        conn = self._connect()
        cursor = conn.cursor()

        timestamp = datetime.now().isoformat()

        # Extract common fields
        event_subtype = kwargs.get('event_subtype')
        snapshot_id = kwargs.get('snapshot_id')
        temp_snapshot_id = kwargs.get('temp_snapshot_id')
        user_action = kwargs.get('user_action')
        source_file = kwargs.get('source_file')
        target_file = kwargs.get('target_file')
        report_week_date = kwargs.get('report_week_date')
        comparison_baseline_id = kwargs.get('comparison_baseline_id')
        comparison_date_from = kwargs.get('comparison_date_from')
        comparison_date_to = kwargs.get('comparison_date_to')
        ops_count_before = kwargs.get('ops_count_before')
        ops_count_after = kwargs.get('ops_count_after')
        new_ops_count = kwargs.get('new_ops_count')
        closed_ops_count = kwargs.get('closed_ops_count')
        status_changes_count = kwargs.get('status_changes_count')
        success = kwargs.get('success', True)
        error_message = kwargs.get('error_message')

        # Store everything else as JSON metadata
        metadata = {k: v for k, v in kwargs.items() if k not in [
            'event_subtype', 'snapshot_id', 'temp_snapshot_id', 'user_action',
            'source_file', 'target_file', 'report_week_date', 'comparison_baseline_id',
            'comparison_date_from', 'comparison_date_to', 'ops_count_before',
            'ops_count_after', 'new_ops_count', 'closed_ops_count',
            'status_changes_count', 'success', 'error_message'
        ]}
        metadata_json = json.dumps(metadata) if metadata else None

        cursor.execute('''
            INSERT INTO audit_log (
                timestamp, event_type, event_subtype, snapshot_id, temp_snapshot_id,
                user_action, source_file, target_file, report_week_date,
                comparison_baseline_id, comparison_date_from, comparison_date_to,
                ops_count_before, ops_count_after, new_ops_count, closed_ops_count,
                status_changes_count, success, error_message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp, event_type, event_subtype, snapshot_id, temp_snapshot_id,
            user_action, source_file, target_file, report_week_date,
            comparison_baseline_id, comparison_date_from, comparison_date_to,
            ops_count_before, ops_count_after, new_ops_count, closed_ops_count,
            status_changes_count, success, error_message, metadata_json
        ))

        audit_id = cursor.lastrowid
        conn.commit()
        conn.close()

        print(f"[AUDIT] {timestamp} | {event_type} | {event_subtype or ''} | ID={audit_id}")
        if not success:
            print(f"[AUDIT] ERROR: {error_message}")

        return audit_id

    def record_data_lineage(self, data_type, source_file_path, **kwargs):
        """
        Record WHERE data came from - CRITICAL for validation

        Args:
            data_type: Type of data (BASELINE, WEEKLY_REPORT, COMPARISON, etc.)
            source_file_path: Full path to source file
            **kwargs: All the lineage metadata
        """
        conn = self._connect()
        cursor = conn.cursor()

        timestamp = datetime.now().isoformat()

        # Calculate file hash for integrity verification
        file_hash = None
        file_size = None
        file_modified = None

        if os.path.exists(source_file_path):
            # Get file hash
            with open(source_file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()

            # Get file metadata
            stat = os.stat(source_file_path)
            file_size = stat.st_size
            file_modified = datetime.fromtimestamp(stat.st_mtime).isoformat()

        # Extract fields
        snapshot_id = kwargs.get('snapshot_id')
        temp_snapshot_id = kwargs.get('temp_snapshot_id')
        source_system = kwargs.get('source_system', 'ACE_REPORT_HUB')
        excel_sheet_name = kwargs.get('excel_sheet_name')
        excel_row_count = kwargs.get('excel_row_count')
        user_provided_date = kwargs.get('user_provided_date')
        system_detected_date = kwargs.get('system_detected_date')
        date_source = kwargs.get('date_source', 'USER_INPUT')  # USER_INPUT or FILE_METADATA
        transformation_applied = kwargs.get('transformation_applied')
        parent_lineage_id = kwargs.get('parent_lineage_id')

        # Store everything else as JSON
        metadata = {k: v for k, v in kwargs.items() if k not in [
            'snapshot_id', 'temp_snapshot_id', 'source_system', 'excel_sheet_name',
            'excel_row_count', 'user_provided_date', 'system_detected_date',
            'date_source', 'transformation_applied', 'parent_lineage_id'
        ]}
        metadata_json = json.dumps(metadata) if metadata else None

        cursor.execute('''
            INSERT INTO data_lineage (
                created_at, data_type, snapshot_id, temp_snapshot_id, source_system,
                source_file_path, source_file_hash, source_file_size, source_file_modified,
                excel_sheet_name, excel_row_count, user_provided_date, system_detected_date,
                date_source, transformation_applied, parent_lineage_id, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp, data_type, snapshot_id, temp_snapshot_id, source_system,
            source_file_path, file_hash, file_size, file_modified,
            excel_sheet_name, excel_row_count, user_provided_date, system_detected_date,
            date_source, transformation_applied, parent_lineage_id, metadata_json
        ))

        lineage_id = cursor.lastrowid
        conn.commit()
        conn.close()

        print(f"[LINEAGE] {timestamp} | {data_type} | File: {os.path.basename(source_file_path)}")
        print(f"[LINEAGE] Source: {source_system} | Date Source: {date_source}")
        print(f"[LINEAGE] User Date: {user_provided_date} | Detected Date: {system_detected_date}")
        print(f"[LINEAGE] Hash: {file_hash[:16]}... | Size: {file_size} bytes")
        print(f"[LINEAGE] Lineage ID: {lineage_id}")

        return lineage_id

    def get_lineage_for_snapshot(self, snapshot_id):
        """Get complete lineage trail for a snapshot"""
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM data_lineage
            WHERE snapshot_id = ?
            ORDER BY created_at DESC
        ''', (snapshot_id,))

        rows = cursor.fetchall()
        conn.close()

        return rows

    def get_audit_trail(self, event_type=None, limit=100):
        """Get audit trail with optional filtering"""
        conn = self._connect()
        cursor = conn.cursor()

        if event_type:
            cursor.execute('''
                SELECT * FROM audit_log
                WHERE event_type = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (event_type, limit))
        else:
            cursor.execute('''
                SELECT * FROM audit_log
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))

        rows = cursor.fetchall()
        conn.close()

        return rows

    def print_audit_summary(self):
        """Print a summary of ALL audit events"""
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT event_type, COUNT(*) as count,
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                   SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failure_count
            FROM audit_log
            GROUP BY event_type
        ''')

        print("\n" + "="*80)
        print("AUDIT TRAIL SUMMARY")
        print("="*80)
        for row in cursor.fetchall():
            event_type, count, success_count, failure_count = row
            print(f"{event_type:30s} | Total: {count:4d} | Success: {success_count:4d} | Failed: {failure_count:4d}")
        print("="*80 + "\n")

        conn.close()
