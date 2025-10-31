#!/usr/bin/env python3
"""
ACE Report Processing Logic
Handles file processing, filtering, and calculations
"""

import pandas as pd
from datetime import datetime
import os


def parse_date(date_str):
    """Parse date string in various formats."""
    if pd.isna(date_str):
        return None

    if isinstance(date_str, datetime):
        return date_str

    date_formats = [
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%m/%d/%Y",
    ]

    for fmt in date_formats:
        try:
            return datetime.strptime(str(date_str), fmt)
        except ValueError:
            continue

    try:
        return pd.to_datetime(date_str)
    except:
        return None


def calculate_days_since_update(last_updated_date):
    """Calculate days since last update from today."""
    if pd.isna(last_updated_date):
        return None

    parsed_date = parse_date(last_updated_date)
    if parsed_date is None:
        return None

    today = datetime.now()
    delta = today - parsed_date
    return delta.days


def get_file_timestamp(filepath):
    """Get the file modification timestamp."""
    if os.path.exists(filepath):
        timestamp = os.path.getmtime(filepath)
        return datetime.fromtimestamp(timestamp)
    return None


def process_ace_file(filepath):
    """
    Process ACE export file and return ALL opportunities with metadata.

    Returns:
        dict with keys:
            - df_all: ALL opportunities (DataFrame) - no filtering
            - df_open: Open opportunities only (for reports)
            - stats: Statistics dict including ARR
    """
    print(f"[PROCESSOR] Reading file: {filepath}")

    # Read Excel file - get ALL ops
    df_all = pd.read_excel(filepath)
    print(f"[PROCESSOR] Total ops in file: {len(df_all)}")

    # Calculate days since last update for ALL ops
    df_all['days_since_update'] = df_all['Last Updated Date'].apply(calculate_days_since_update)

    # Define "open" ops for reporting (but store ALL in database)
    valid_statuses = ['Approved', 'In review', 'Draft', 'Submitted']
    valid_stages = ['Prospect', 'Qualified', 'Committed', 'Business Validation']

    df_open = df_all[
        df_all['Status'].isin(valid_statuses) &
        df_all['Stage'].isin(valid_stages)
    ].copy()

    print(f"[PROCESSOR] Open ops (for reporting): {len(df_open)} opportunities")

    # Get file metadata
    file_date = get_file_timestamp(filepath)
    file_name = os.path.basename(filepath)

    # Calculate ARR for open ops only
    arr_column = 'Estimated AWS Monthly Recurring Revenue'
    total_arr = df_open[arr_column].fillna(0).sum()

    # CRITICAL FIX: Filter out excluded ops for WA/RAPID counts to match email tables
    # Email generator filters these out, so stats must match what's shown in tables
    from ace_database import EXCLUDED_OPS
    df_reportable = df_open[~df_open['Opportunity id'].isin(EXCLUDED_OPS)]

    # Count Well-Architected opportunities (check APN Programs field) - REPORTABLE ONLY
    wa_count = 0
    if 'APN Programs' in df_reportable.columns:
        wa_count = len(df_reportable[df_reportable['APN Programs'].fillna('').str.contains('Well-Architected', case=False, na=False)])

    # Count RAPID PILOT opportunities (check Partner Project Title field) - REPORTABLE ONLY
    rapid_count = 0
    if 'Partner Project Title' in df_reportable.columns:
        rapid_count = len(df_reportable[df_reportable['Partner Project Title'].fillna('').str.contains('RAPID PILOT', case=False, na=False)])

    # Calculate statistics
    avg_days = df_open['days_since_update'].mean() if len(df_open) > 0 else 0
    stale_count = len(df_open[df_open['days_since_update'] > 30])

    stats = {
        'total_all_ops': len(df_all),
        'total_open': len(df_open),
        'avg_days_since_update': round(avg_days, 1) if avg_days else 0,
        'stale_count': stale_count,
        'total_arr': round(total_arr, 2),
        'well_architected_count': wa_count,
        'rapid_pilot_count': rapid_count,
        'file_name': file_name,
        'file_date': file_date,
        'processed_date': datetime.now()
    }

    print(f"[PROCESSOR] Processing complete:")
    print(f"[PROCESSOR]   - Total ALL ops: {stats['total_all_ops']}")
    print(f"[PROCESSOR]   - Total open ops: {stats['total_open']}")
    print(f"[PROCESSOR]   - Total ARR: ${stats['total_arr']:,.2f}")
    print(f"[PROCESSOR]   - Avg days since update: {stats['avg_days_since_update']}")
    print(f"[PROCESSOR]   - Stale ops (30+ days): {stats['stale_count']}")

    return {
        'df_all': df_all,  # ALL ops - no filtering
        'df_open': df_open,  # Open ops only
        'stats': stats
    }


def get_stale_opportunities(df, days_threshold=30):
    """Filter opportunities not updated in X days."""
    df_filtered = df[df['days_since_update'].notna()].copy()
    df_stale = df_filtered[df_filtered['days_since_update'] > days_threshold]

    print(f"[PROCESSOR] Found {len(df_stale)} stale opportunities (>{days_threshold} days)")
    return df_stale
