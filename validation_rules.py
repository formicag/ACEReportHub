#!/usr/bin/env python3
"""
VALIDATION RULES ENGINE
Critical business report validation - ZERO TOLERANCE for bad data
"""

import re
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple


class ValidationRule:
    """Single validation rule definition"""

    def __init__(self, rule_id, name, description, field, rule_type,
                 rule_value, severity, enabled=True, error_message=None):
        self.rule_id = rule_id
        self.name = name
        self.description = description
        self.field = field  # Which column to validate
        self.rule_type = rule_type  # 'required', 'range', 'format', 'logic'
        self.rule_value = rule_value  # JSON with rule parameters
        self.severity = severity  # 'ERROR', 'WARNING', 'INFO'
        self.enabled = enabled
        self.error_message = error_message


class ValidationEngine:
    """
    VALIDATION ENGINE - The Guardian of Data Quality

    This engine BLOCKS bad data from entering reports.
    """

    def __init__(self, db_path):
        self.db_path = db_path
        self._ensure_validation_tables()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _ensure_validation_tables(self):
        """Create validation tables if they don't exist"""
        conn = self._connect()
        cursor = conn.cursor()

        # Table: validation_rules
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS validation_rules (
                rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                field TEXT NOT NULL,
                rule_type TEXT NOT NULL,
                rule_value TEXT,
                severity TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                error_message TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        ''')

        # Table: validation_results
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS validation_results (
                validation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER,
                rule_id INTEGER,
                opportunity_id TEXT,
                field TEXT,
                severity TEXT,
                error_message TEXT,
                actual_value TEXT,
                expected_value TEXT,
                validated_at TEXT,
                FOREIGN KEY (snapshot_id) REFERENCES weekly_snapshots(snapshot_id),
                FOREIGN KEY (rule_id) REFERENCES validation_rules(rule_id)
            )
        ''')

        conn.commit()
        conn.close()

        # Load default rules if table is empty
        self._load_default_rules()

    def _load_default_rules(self):
        """Load default validation rules on first run"""
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM validation_rules')
        if cursor.fetchone()[0] > 0:
            conn.close()
            return  # Rules already loaded

        now = datetime.now().isoformat()

        default_rules = [
            # CRITICAL BUSINESS RULES
            ('Total Ops Not Zero', 'Total open opportunities must be > 0', 'COUNT', 'range',
             '{"min": 1, "max": 150}', 'ERROR', 1, 'Open opportunities count is {actual}. Must be between 1 and 150.'),

            ('Total Ops Not Excessive', 'Total open opportunities must be <= 150', 'COUNT', 'range',
             '{"min": 1, "max": 150}', 'ERROR', 1, 'Too many open opportunities: {actual}. Maximum allowed is 150.'),

            # OPPORTUNITY-LEVEL RULES
            ('Opportunity Code Required', 'Every opportunity must have a code', 'Opportunity ID', 'required',
             '{}', 'ERROR', 1, 'Opportunity is missing Opportunity ID'),

            ('Opportunity Code Format', 'Opportunity code must match format', 'Opportunity ID', 'format',
             '{"pattern": "^[A-Z0-9-]{5,50}$"}', 'ERROR', 1, 'Opportunity ID "{actual}" has invalid format'),

            ('Project Name Required', 'Every opportunity must have a project name', 'Opportunity Name', 'required',
             '{}', 'ERROR', 1, 'Opportunity {opp_id} is missing Project Name'),

            ('Project Name Not Empty', 'Project name cannot be empty or whitespace', 'Opportunity Name', 'not_empty',
             '{}', 'ERROR', 1, 'Opportunity {opp_id} has empty Project Name'),

            ('ARR Not Zero', 'Estimated ARR must be greater than 0', 'ARR (USD)', 'range',
             '{"min": 0.01, "max": 999999999}', 'ERROR', 1, 'Opportunity {opp_id} has ARR of {actual}. Must be > 0.'),

            ('ARR Not Negative', 'ARR cannot be negative', 'ARR (USD)', 'range',
             '{"min": 0, "max": 999999999}', 'ERROR', 1, 'Opportunity {opp_id} has negative ARR: {actual}'),

            ('Created Date Required', 'Created date must exist', 'CreatedDate', 'required',
             '{}', 'ERROR', 1, 'Opportunity {opp_id} is missing Created Date'),

            ('Created Date Valid', 'Created date must be valid date', 'CreatedDate', 'date_valid',
             '{}', 'ERROR', 1, 'Opportunity {opp_id} has invalid Created Date: {actual}'),

            ('Created By Required', 'Created by name must exist', 'CreatedBy', 'required',
             '{}', 'ERROR', 1, 'Opportunity {opp_id} is missing Created By name'),

            ('Last Updated Required', 'Last updated date must exist', 'LastModifiedDate', 'required',
             '{}', 'ERROR', 1, 'Opportunity {opp_id} is missing Last Updated Date'),

            ('Last Updated Not Future', 'Last updated date cannot be in future', 'LastModifiedDate', 'date_not_future',
             '{}', 'ERROR', 1, 'Opportunity {opp_id} has future Last Updated Date: {actual}'),

            ('Date Logic', 'Created date must be <= Last updated date', 'CreatedDate,LastModifiedDate', 'date_logic',
             '{}', 'ERROR', 1, 'Opportunity {opp_id}: Created date ({actual}) is after Last Updated date'),

            ('Stage Required', 'Stage must exist', 'Stage', 'required',
             '{}', 'ERROR', 1, 'Opportunity {opp_id} is missing Stage'),

            ('Owner Required', 'Owner must exist', 'Owner', 'required',
             '{}', 'WARNING', 1, 'Opportunity {opp_id} is missing Owner'),

            ('Customer Name Required', 'Customer name must exist', 'Account Name', 'required',
             '{}', 'ERROR', 1, 'Opportunity {opp_id} is missing Customer/Account Name'),

            # DATA QUALITY WARNINGS
            ('Days Since Update Reasonable', 'Days since update should be < 90', 'days_since_update', 'range',
             '{"min": 0, "max": 90}', 'WARNING', 1, 'Opportunity {opp_id} has not been updated in {actual} days'),

            ('Stale Opportunity', 'Flag opportunities not updated in 30+ days', 'days_since_update', 'range',
             '{"min": 0, "max": 30}', 'WARNING', 1, 'Opportunity {opp_id} is stale ({actual} days since update)'),

            ('Duplicate Opportunity ID', 'No duplicate opportunity IDs allowed', 'Opportunity ID', 'unique',
             '{}', 'ERROR', 1, 'Duplicate Opportunity ID found: {actual}'),
        ]

        for rule in default_rules:
            cursor.execute('''
                INSERT INTO validation_rules
                (name, description, field, rule_type, rule_value, severity, enabled, error_message, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', rule + (now, now))

        conn.commit()
        conn.close()
        print("[VALIDATION] Loaded default validation rules")

    def validate_dataframe(self, df, snapshot_id=None) -> Dict[str, Any]:
        """
        Validate entire dataframe against all rules

        Returns:
            {
                'valid': True/False,
                'error_count': int,
                'warning_count': int,
                'errors': [...],
                'warnings': [...],
                'summary': {...}
            }
        """
        print("\n" + "="*80)
        print("VALIDATION ENGINE - SCANNING DATA")
        print("="*80)

        results = {
            'valid': True,
            'error_count': 0,
            'warning_count': 0,
            'info_count': 0,
            'errors': [],
            'warnings': [],
            'info': [],
            'summary': {}
        }

        # Get all enabled rules
        rules = self.get_all_rules(enabled_only=True)

        print(f"[VALIDATION] Loaded {len(rules)} validation rules")
        print(f"[VALIDATION] Validating {len(df)} opportunities...")

        # AGGREGATE VALIDATIONS (whole dataset)
        total_ops = len(df)

        # Rule: Total ops count
        for rule in rules:
            if rule['field'] == 'COUNT' and rule['rule_type'] == 'range':
                import json
                rule_val = json.loads(rule['rule_value'])
                min_val = rule_val.get('min', 0)
                max_val = rule_val.get('max', 999999)

                if total_ops < min_val or total_ops > max_val:
                    error_msg = rule['error_message'].format(actual=total_ops)
                    self._add_validation_result(results, rule, None, 'COUNT', total_ops,
                                                f"{min_val}-{max_val}", error_msg, snapshot_id)

        # ROW-LEVEL VALIDATIONS
        seen_ids = set()

        for idx, row in df.iterrows():
            opp_id = row.get('Opportunity ID', f'ROW_{idx}')

            # Check for duplicates
            if opp_id in seen_ids:
                rule = next((r for r in rules if r['rule_type'] == 'unique'), None)
                if rule:
                    error_msg = rule['error_message'].format(actual=opp_id, opp_id=opp_id)
                    self._add_validation_result(results, rule, opp_id, 'Opportunity ID', opp_id,
                                                'unique', error_msg, snapshot_id)
            seen_ids.add(opp_id)

            # Validate each rule
            for rule in rules:
                if rule['field'] == 'COUNT':
                    continue  # Already validated

                self._validate_row(row, rule, results, snapshot_id)

        # Print summary
        print("\n" + "="*80)
        print("VALIDATION RESULTS")
        print("="*80)
        print(f"Errors:   {results['error_count']}")
        print(f"Warnings: {results['warning_count']}")
        print(f"Info:     {results['info_count']}")

        if results['error_count'] > 0:
            results['valid'] = False
            print("\n❌ VALIDATION FAILED - CRITICAL ERRORS FOUND")
            print("="*80)
            for err in results['errors'][:10]:  # Show first 10
                print(f"  - {err['message']}")
            if len(results['errors']) > 10:
                print(f"  ... and {len(results['errors']) - 10} more errors")
        else:
            print("\n✅ VALIDATION PASSED - No critical errors")

        if results['warning_count'] > 0:
            print(f"\n⚠️  {results['warning_count']} warnings found (data quality issues)")

        print("="*80 + "\n")

        return results

    def _validate_row(self, row, rule, results, snapshot_id):
        """Validate a single row against a rule"""
        import json

        field = rule['field']
        opp_id = row.get('Opportunity ID', 'UNKNOWN')

        # Get field value
        if ',' in field:
            # Multi-field rule (e.g., date logic)
            fields = [f.strip() for f in field.split(',')]
            values = [row.get(f) for f in fields]
        else:
            value = row.get(field)

        # Apply rule type
        rule_type = rule['rule_type']
        rule_value = json.loads(rule['rule_value']) if rule['rule_value'] else {}

        failed = False
        error_msg = rule['error_message']
        actual_val = None
        expected_val = None

        if rule_type == 'required':
            if field not in row or row[field] is None or (isinstance(row[field], str) and not row[field].strip()):
                failed = True
                actual_val = 'NULL'
                expected_val = 'NOT NULL'

        elif rule_type == 'not_empty':
            if field in row and isinstance(row[field], str) and not row[field].strip():
                failed = True
                actual_val = 'EMPTY'
                expected_val = 'NOT EMPTY'

        elif rule_type == 'range':
            if field in row and row[field] is not None:
                try:
                    val = float(row[field])
                    min_val = rule_value.get('min', -999999999)
                    max_val = rule_value.get('max', 999999999)

                    if val < min_val or val > max_val:
                        failed = True
                        actual_val = val
                        expected_val = f"{min_val}-{max_val}"
                except (ValueError, TypeError):
                    pass

        elif rule_type == 'format':
            if field in row and row[field] is not None:
                pattern = rule_value.get('pattern', '')
                if pattern and not re.match(pattern, str(row[field])):
                    failed = True
                    actual_val = row[field]
                    expected_val = f"Pattern: {pattern}"

        elif rule_type == 'date_valid':
            if field in row and row[field] is not None:
                try:
                    from dateutil import parser
                    parser.parse(str(row[field]))
                except:
                    failed = True
                    actual_val = row[field]
                    expected_val = 'Valid date'

        elif rule_type == 'date_not_future':
            if field in row and row[field] is not None:
                try:
                    from dateutil import parser
                    date_val = parser.parse(str(row[field]))
                    if date_val > datetime.now():
                        failed = True
                        actual_val = row[field]
                        expected_val = '<= today'
                except:
                    pass

        elif rule_type == 'date_logic':
            # Created <= Last Updated
            if len(values) == 2 and all(v is not None for v in values):
                try:
                    from dateutil import parser
                    date1 = parser.parse(str(values[0]))
                    date2 = parser.parse(str(values[1]))
                    if date1 > date2:
                        failed = True
                        actual_val = values[0]
                        expected_val = f'<= {values[1]}'
                except:
                    pass

        if failed:
            # Format error message
            error_msg = error_msg.format(
                opp_id=opp_id,
                actual=actual_val if actual_val is not None else 'NULL',
                expected=expected_val if expected_val is not None else ''
            )
            self._add_validation_result(results, rule, opp_id, field, actual_val, expected_val, error_msg, snapshot_id)

    def _add_validation_result(self, results, rule, opp_id, field, actual_val, expected_val, error_msg, snapshot_id):
        """Add validation result to results dict"""
        severity = rule['severity']

        result = {
            'rule_id': rule['rule_id'],
            'rule_name': rule['name'],
            'opportunity_id': opp_id,
            'field': field,
            'severity': severity,
            'message': error_msg,
            'actual_value': str(actual_val) if actual_val is not None else None,
            'expected_value': str(expected_val) if expected_val is not None else None
        }

        if severity == 'ERROR':
            results['errors'].append(result)
            results['error_count'] += 1
        elif severity == 'WARNING':
            results['warnings'].append(result)
            results['warning_count'] += 1
        else:
            results['info'].append(result)
            results['info_count'] += 1

        # Save to database if snapshot_id provided
        if snapshot_id:
            self._save_validation_result(snapshot_id, rule['rule_id'], opp_id, field, severity,
                                         error_msg, actual_val, expected_val)

    def _save_validation_result(self, snapshot_id, rule_id, opp_id, field, severity, error_msg, actual_val, expected_val):
        """Save validation result to database"""
        conn = self._connect()
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute('''
            INSERT INTO validation_results
            (snapshot_id, rule_id, opportunity_id, field, severity, error_message, actual_value, expected_value, validated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (snapshot_id, rule_id, opp_id, field, severity, error_msg,
              str(actual_val) if actual_val else None,
              str(expected_val) if expected_val else None, now))

        conn.commit()
        conn.close()

    def get_all_rules(self, enabled_only=False):
        """Get all validation rules"""
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if enabled_only:
            cursor.execute('SELECT * FROM validation_rules WHERE enabled = 1 ORDER BY severity DESC, name')
        else:
            cursor.execute('SELECT * FROM validation_rules ORDER BY severity DESC, name')

        rules = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rules

    def add_rule(self, name, description, field, rule_type, rule_value, severity, error_message):
        """Add new validation rule"""
        conn = self._connect()
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute('''
            INSERT INTO validation_rules
            (name, description, field, rule_type, rule_value, severity, enabled, error_message, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
        ''', (name, description, field, rule_type, rule_value, severity, error_message, now, now))

        rule_id = cursor.lastrowid
        conn.commit()
        conn.close()

        print(f"[VALIDATION] Added rule: {name}")
        return rule_id

    def update_rule(self, rule_id, **kwargs):
        """Update validation rule"""
        conn = self._connect()
        cursor = conn.cursor()

        now = datetime.now().isoformat()
        kwargs['updated_at'] = now

        set_clause = ', '.join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [rule_id]

        cursor.execute(f'UPDATE validation_rules SET {set_clause} WHERE rule_id = ?', values)

        conn.commit()
        conn.close()

        print(f"[VALIDATION] Updated rule ID: {rule_id}")

    def delete_rule(self, rule_id):
        """Delete validation rule"""
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM validation_rules WHERE rule_id = ?', (rule_id,))

        conn.commit()
        conn.close()

        print(f"[VALIDATION] Deleted rule ID: {rule_id}")

    def get_validation_results(self, snapshot_id):
        """Get validation results for a snapshot"""
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT vr.*, r.name as rule_name, r.description as rule_description
            FROM validation_results vr
            JOIN validation_rules r ON vr.rule_id = r.rule_id
            WHERE vr.snapshot_id = ?
            ORDER BY vr.severity DESC, vr.validated_at DESC
        ''', (snapshot_id,))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
