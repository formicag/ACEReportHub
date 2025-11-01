#!/usr/bin/env python3
"""
Email Generator for ACE Report - Flask Version
Generates HTML emails with formatted opportunity tables and comparisons
"""

import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from email_config import EMAIL_CONFIG, SMTP_CONFIG, DAYS_THRESHOLD
from ace_database import EXCLUDED_OPS
from bedrock_client import generate_intro_message


def generate_insights_section(df_open):
    """Generate insights section with RAPID pilots, AI projects, top spenders, etc."""
    # Filter out excluded ops
    df_reportable = df_open[~df_open['Opportunity id'].isin(EXCLUDED_OPS)]

    html = '<div class="insights-section">\n'
    html += '<h2>📊 Key Insights for Open Opportunities</h2>\n'

    # 1. Top 3 by estimated monthly spend
    arr_column = 'Estimated AWS Monthly Recurring Revenue'
    if arr_column in df_reportable.columns:
        top_spend = df_reportable.nlargest(3, arr_column)
        top_spend_filtered = [(row['Customer Company Name'], row['Opportunity id'], row[arr_column])
                             for _, row in top_spend.iterrows()
                             if pd.notna(row[arr_column]) and row[arr_column] > 0]

        if top_spend_filtered:
            html += '<h3>💰 Top 3 Opportunities by Est. Monthly Spend</h3>\n'
            html += '<table class="opportunities-table">\n'
            html += '<thead><tr><th>Rank</th><th>Customer</th><th>Opportunity ID</th><th>Est. Monthly Spend</th></tr></thead>\n'
            html += '<tbody>\n'
            for idx, (customer, opp_id, spend) in enumerate(top_spend_filtered, 1):
                html += f'<tr><td>{idx}</td><td>{customer}</td><td>{opp_id}</td><td>${spend:,.0f}</td></tr>\n'
            html += '</tbody></table>\n'

    # 2. RAPID PILOT opportunities
    rapid_ops = df_reportable[df_reportable['Partner Project Title'].str.contains('RAPID PILOT', case=False, na=False)]
    if len(rapid_ops) > 0:
        html += f'<h3>🚀 RAPID PILOT Opportunities ({len(rapid_ops)})</h3>\n'
        html += '<table class="opportunities-table">\n'
        html += '<thead><tr><th>Customer</th><th>Opportunity ID</th><th>Stage</th></tr></thead>\n'
        html += '<tbody>\n'
        for _, row in rapid_ops.iterrows():
            html += f'<tr><td>{row["Customer Company Name"]}</td><td>{row["Opportunity id"]}</td><td>{row.get("Stage", "")}</td></tr>\n'
        html += '</tbody></table>\n'

    # 3. Well-Architected opportunities (check APN Programs field)
    wa_ops = df_reportable[df_reportable['APN Programs'].fillna('').str.contains('Well-Architected', case=False, na=False)]
    if len(wa_ops) > 0:
        html += f'<h3>🏗️ Well-Architected Opportunities ({len(wa_ops)})</h3>\n'
        html += '<table class="opportunities-table">\n'
        html += '<thead><tr><th>Customer</th><th>Opportunity ID</th><th>Stage</th></tr></thead>\n'
        html += '<tbody>\n'
        for _, row in wa_ops.iterrows():
            html += f'<tr><td>{row["Customer Company Name"]}</td><td>{row["Opportunity id"]}</td><td>{row.get("Stage", "")}</td></tr>\n'
        html += '</tbody></table>\n'

    html += '</div>\n'
    return html


def generate_summary_section(current_stats, previous_stats=None):
    """Generate summary statistics HTML section."""
    html = '<div class="summary-section">\n'
    html += '<h2>📊 Weekly Summary</h2>\n'

    # Consecutive weeks with no stale ops (ACE Hygiene metric) - show prominently if > 0
    consecutive_weeks = current_stats.get('consecutive_weeks_no_stale', 0)
    if consecutive_weeks > 0:
        html += '<div style="background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">\n'
        html += '<div style="font-size: 48px; font-weight: bold; margin-bottom: 10px;">🎉</div>\n'
        html += f'<div style="font-size: 32px; font-weight: bold; margin-bottom: 5px;">{consecutive_weeks} {"Week" if consecutive_weeks == 1 else "Weeks"}</div>\n'
        html += '<div style="font-size: 18px; opacity: 0.95;">With No Stale Opportunities</div>\n'
        html += '<div style="font-size: 14px; opacity: 0.9; margin-top: 10px;">Excellent ACE Hygiene! 🌟</div>\n'
        html += '</div>\n'

    html += '<div class="stats-grid">\n'

    # Total open ops (more is good = green up, less is neutral = black down)
    total = current_stats['total_reportable_ops']
    if previous_stats:
        prev_total = previous_stats['total_reportable_ops']
        delta = total - prev_total
        arrow = "↑" if delta > 0 else "↓" if delta < 0 else "→"
        color = "green" if delta > 0 else "black" if delta < 0 else "gray"
        html += f'<div class="stat-box">'
        html += f'<div class="stat-label">Total Open Opportunities</div>'
        html += f'<div class="stat-value">{total} <span style="color: {color}">{arrow} {abs(delta)}</span></div>'
        html += f'<div class="stat-prev">Last report: {prev_total}</div>'
        html += f'</div>\n'
    else:
        html += f'<div class="stat-box">'
        html += f'<div class="stat-label">Total Open Opportunities</div>'
        html += f'<div class="stat-value">{total}</div>'
        html += f'</div>\n'

    # Average days
    avg = current_stats['avg_days_since_update']
    if previous_stats:
        prev_avg = previous_stats['avg_days_since_update']
        delta = avg - prev_avg
        arrow = "↑" if delta > 0 else "↓" if delta < 0 else "→"
        color = "red" if delta > 0 else "green" if delta < 0 else "gray"
        html += f'<div class="stat-box">'
        html += f'<div class="stat-label">Average Days Since Update</div>'
        html += f'<div class="stat-value">{avg:.1f} <span style="color: {color}">{arrow} {abs(delta):.1f}</span></div>'
        html += f'<div class="stat-prev">Last report: {prev_avg:.1f}</div>'
        html += f'</div>\n'
    else:
        html += f'<div class="stat-box">'
        html += f'<div class="stat-label">Average Days Since Update</div>'
        html += f'<div class="stat-value">{avg:.1f}</div>'
        html += f'</div>\n'

    # Stale ops
    stale = current_stats['stale_ops_count']
    if previous_stats:
        prev_stale = previous_stats['stale_ops_count']
        delta = stale - prev_stale
        arrow = "↑" if delta > 0 else "↓" if delta < 0 else "→"
        color = "red" if delta > 0 else "green" if delta < 0 else "gray"
        html += f'<div class="stat-box">'
        html += f'<div class="stat-label">Stale Opportunities (30+ days)</div>'
        html += f'<div class="stat-value">{stale} <span style="color: {color}">{arrow} {abs(delta)}</span></div>'
        html += f'<div class="stat-prev">Last report: {prev_stale}</div>'
        html += f'</div>\n'
    else:
        html += f'<div class="stat-box">'
        html += f'<div class="stat-label">Stale Opportunities (30+ days)</div>'
        html += f'<div class="stat-value">{stale}</div>'
        html += f'</div>\n'

    # Total ARR (increase is good = green up, decrease is neutral = black down)
    arr = current_stats.get('total_arr', 0)
    if previous_stats and 'total_arr' in previous_stats:
        prev_arr = previous_stats.get('total_arr', 0)
        delta = arr - prev_arr
        arrow = "↑" if delta > 0 else "↓" if delta < 0 else "→"
        color = "green" if delta > 0 else "black" if delta < 0 else "gray"  # CHANGED: green up, black down
        html += f'<div class="stat-box">'
        html += f'<div class="stat-label">Est. Monthly ARR (Open Ops)</div>'
        html += f'<div class="stat-value">${arr:,.0f} <span style="color: {color}">{arrow} ${abs(delta):,.0f}</span></div>'
        html += f'<div class="stat-prev">Last report: ${prev_arr:,.0f}</div>'  # CHANGED: "Last report" instead of "Last week"
        html += f'</div>\n'
    else:
        html += f'<div class="stat-box">'
        html += f'<div class="stat-label">Est. Monthly ARR (Open Ops)</div>'
        html += f'<div class="stat-value">${arr:,.0f}</div>'
        html += f'</div>\n'

    html += '</div>\n</div>\n'
    return html


def generate_changes_section(comparison_data):
    """Generate opportunity changes HTML section."""
    if not comparison_data:
        return ""

    new_ops = comparison_data.get('new_ops', pd.DataFrame())
    closed_ops = comparison_data.get('closed_ops', pd.DataFrame())
    status_changes = comparison_data.get('status_changes', [])

    # Filter out excluded ops
    new_ops = new_ops[~new_ops['Opportunity id'].isin(EXCLUDED_OPS)]

    html = '<div class="changes-section">\n'

    # New opportunities
    if len(new_ops) > 0:
        html += '<h2>✨ New Opportunities Created in ACE Since Last Report</h2>\n'
        html += f'<p>These <strong>{len(new_ops)} new opportunities</strong> were added to ACE since last report.</p>\n'
        html += '<p style="color: #d32f2f;"><em>Please add a primary contact to opportunities without a contact.</em></p>\n'
        html += '<table class="opportunities-table">\n'
        html += '<thead><tr>'
        html += '<th>Opportunity ID</th><th>Customer</th><th>Stage</th><th>Date Created</th><th>Primary Contact</th><th>Created By</th><th>Est. Monthly ARR</th>'
        html += '</tr></thead>\n<tbody>\n'

        for _, row in new_ops.iterrows():
            html += '<tr>'
            html += f'<td>{row["Opportunity id"]}</td>'
            html += f'<td>{row.get("Customer Company Name", "")}</td>'
            html += f'<td>{row.get("Stage", "")}</td>'

            # Date Created
            date_created = row.get("Date Created", "")
            if pd.notna(date_created) and date_created:
                try:
                    date_created = pd.to_datetime(date_created, errors='coerce')
                    if pd.notna(date_created):
                        date_created = date_created.strftime('%d/%m/%Y')
                    else:
                        date_created = ""
                except:
                    date_created = ""
            else:
                date_created = ""
            html += f'<td>{date_created}</td>'

            # Primary contact - show empty string instead of nan
            primary_contact = row.get("Primary Contact Name", "")
            if pd.isna(primary_contact) or str(primary_contact).lower() == 'nan':
                primary_contact = ""
            html += f'<td>{primary_contact}</td>'

            # Created By column
            created_by = row.get("Created By", "")
            if pd.isna(created_by):
                created_by = ""
            html += f'<td>{created_by}</td>'

            # Estimated Monthly ARR
            arr = row.get("Estimated AWS Monthly Recurring Revenue", 0)
            if pd.isna(arr):
                arr = 0
            html += f'<td>${arr:,.0f}</td>'

            html += '</tr>\n'

        html += '</tbody></table>\n'

    # Status changes - Launched (filter out excluded ops)
    launched = [c for c in status_changes if c['new_stage'] == 'Launched' and c['opportunity_id'] not in EXCLUDED_OPS]
    if launched:
        # Check for launched ops missing AWS Account ID
        launched_missing_aws_id = [c for c in launched if not c.get('aws_account_id') or str(c.get('aws_account_id', '')).strip() == '' or str(c.get('aws_account_id', '')).lower() == 'nan']

        html += '<h2>🚀 Launched Ops This Week</h2>\n'
        html += f'<p>These <strong>{len(launched)} opportunities</strong> have been moved to launched in ACE.</p>\n'

        # WARNING: Launched ops missing AWS Account ID
        if launched_missing_aws_id:
            html += '<div style="background-color: #ffebee; padding: 10px; border-left: 4px solid #d32f2f; margin: 15px 0; border-radius: 4px;">\n'
            html += f'<p style="margin: 0; color: #d32f2f;"><strong>⚠️ WARNING: {len(launched_missing_aws_id)} launched opportunity(ies) missing AWS Account ID!</strong><br>'
            html += 'These opportunities were launched WITHOUT an AWS Account ID and will NOT count toward LARR metrics:<br>'
            for c in launched_missing_aws_id:
                html += f'<strong>{c["opportunity_id"]}</strong> ({c["customer_name"]}), '
            html = html.rstrip(', ')
            html += '<br>This should NEVER happen. Please add AWS Account IDs immediately.</p>\n'
            html += '</div>\n'

        html += '<table class="opportunities-table">\n'
        html += '<thead><tr>'
        html += '<th>Opportunity ID</th><th>Partner Project Title</th><th>Customer</th><th>Previous Stage</th><th>Created By</th><th>Est. Monthly ARR</th><th>AWS Sales Rep Name</th><th>AWS Account ID</th>'
        html += '</tr></thead>\n<tbody>\n'

        for change in launched:
            # Highlight row if missing AWS Account ID
            row_style = ''
            if not change.get('aws_account_id') or str(change.get('aws_account_id', '')).strip() == '' or str(change.get('aws_account_id', '')).lower() == 'nan':
                row_style = ' style="background-color: #ffebee;"'

            html += f'<tr{row_style}>'
            html += f'<td><strong>{change["opportunity_id"]}</strong></td>'

            # Partner Project Title
            project_title = change.get('partner_project_title', '')
            if pd.isna(project_title):
                project_title = ''
            html += f'<td>{project_title}</td>'

            html += f'<td>{change["customer_name"]}</td>'
            html += f'<td>{change["old_stage"]}</td>'

            # Created By
            created_by = change.get('created_by', '')
            if pd.isna(created_by):
                created_by = ''
            html += f'<td>{created_by}</td>'

            # Estimated Monthly ARR
            arr = change.get('estimated_revenue', 0)
            if pd.isna(arr):
                arr = 0
            html += f'<td>${arr:,.0f}</td>'

            # AWS Sales Rep Name
            aws_rep = change.get('aws_sales_rep_name', '')
            if pd.isna(aws_rep):
                aws_rep = ''
            html += f'<td>{aws_rep}</td>'

            # AWS Account ID
            aws_account_id = change.get('aws_account_id', '')
            if pd.isna(aws_account_id) or str(aws_account_id).strip() == '' or str(aws_account_id).lower() == 'nan':
                aws_account_id = '<span style="color: #d32f2f; font-weight: bold;">MISSING</span>'
            html += f'<td>{aws_account_id}</td>'

            html += '</tr>\n'

        html += '</tbody></table>\n'

    # Status changes - Closed Lost (filter out excluded ops)
    closed_lost = [c for c in status_changes if c['new_stage'] == 'Closed Lost' and c['opportunity_id'] not in EXCLUDED_OPS]
    if closed_lost:
        html += '<h2>❌ Closed Lost Ops This Week</h2>\n'
        html += f'<p>These <strong>{len(closed_lost)} opportunities</strong> were marked as Closed Lost. Please ensure the close reason is documented.</p>\n'
        html += '<table class="opportunities-table">\n'
        html += '<thead><tr>'
        html += '<th>Opportunity ID</th><th>Customer</th><th>Close Reason</th><th>Est. Monthly ARR</th><th>Last Updated</th>'
        html += '</tr></thead>\n<tbody>\n'

        for change in closed_lost:
            html += '<tr>'
            html += f'<td><strong>{change["opportunity_id"]}</strong></td>'
            html += f'<td>{change["customer_name"]}</td>'

            # Close Reason from ACE data
            close_reason = change.get('close_reason', '')
            if pd.isna(close_reason) or not close_reason:
                close_reason = 'Not specified'
            html += f'<td>{close_reason}</td>'

            # Estimated Monthly ARR
            arr = change.get('estimated_revenue', 0)
            if pd.isna(arr):
                arr = 0
            html += f'<td>${arr:,.0f}</td>'

            # Last Updated Date
            last_updated = change.get('last_updated_date', '')
            if pd.notna(last_updated) and last_updated:
                try:
                    last_updated = pd.to_datetime(last_updated, errors='coerce')
                    if pd.notna(last_updated):
                        last_updated = last_updated.strftime('%d/%m/%Y')
                    else:
                        last_updated = ''
                except:
                    last_updated = ''
            else:
                last_updated = ''
            html += f'<td>{last_updated}</td>'

            html += '</tr>\n'

        html += '</tbody></table>\n'

    # Closed/No longer open
    if len(closed_ops) > 0:
        # Filter out excluded ops
        closed_reportable = [op for op in closed_ops if op['opportunity_id'] not in EXCLUDED_OPS]

        if len(closed_reportable) > 0:
            html += '<h2>🔒 ACE Ops No Longer Open Since Last Report</h2>\n'
            html += f'<p>These <strong>{len(closed_reportable)} opportunities</strong> were open in the last report but are no longer in the open pipeline:</p>\n'
            html += '<table class="opportunities-table">\n'
            html += '<thead><tr>'
            html += '<th>Opportunity ID</th><th>Customer</th><th>Previous Stage</th><th>Current Stage</th>'
            html += '</tr></thead>\n<tbody>\n'

            for op in closed_reportable:
                html += '<tr>'
                html += f'<td><strong>{op["opportunity_id"]}</strong></td>'
                html += f'<td>{op.get("customer_name", "")}</td>'
                html += f'<td>{op.get("previous_stage", "Unknown")}</td>'
                html += f'<td><em>{op.get("current_stage", "Not in report")}</em></td>'
                html += '</tr>\n'

            html += '</tbody></table>\n'

    html += '</div>\n'
    return html


def generate_stale_ops_table(df_stale):
    """Generate HTML table for stale opportunities."""
    # Filter out excluded ops
    df_stale_reportable = df_stale[~df_stale['Opportunity id'].isin(EXCLUDED_OPS)]

    if len(df_stale_reportable) == 0:
        return "<p><em>Great news! No opportunities have been stale for more than 30 days.</em></p>"

    html = '<table class="opportunities-table">\n'
    html += '<thead><tr>'
    html += '<th>Opportunity ID</th>'
    html += '<th>Days Since Update</th>'
    html += '<th>Customer</th>'
    html += '<th>Status</th>'
    html += '<th>Stage</th>'
    html += '<th>Primary Contact</th>'
    html += '<th>Last Updated</th>'
    html += '<th>Next Step</th>'
    html += '</tr></thead>\n<tbody>\n'

    for _, row in df_stale_reportable.iterrows():
        html += '<tr>'
        html += f'<td>{row["Opportunity id"]}</td>'
        html += f'<td style="font-weight: bold; color: #d32f2f;">{int(row["days_since_update"])}</td>'
        html += f'<td>{row.get("Customer Company Name", "")}</td>'
        html += f'<td>{row.get("Status", "")}</td>'
        html += f'<td>{row.get("Stage", "")}</td>'
        html += f'<td>{row.get("Primary Contact Name", "")}</td>'

        last_updated = row.get("Last Updated Date", "")
        if pd.notna(last_updated):
            last_updated = pd.to_datetime(last_updated, errors='coerce')
            if pd.notna(last_updated):
                last_updated = last_updated.strftime('%d/%m/%Y')
        html += f'<td>{last_updated}</td>'

        html += f'<td>{row.get("Next Step", "")}</td>'
        html += '</tr>\n'

    html += '</tbody></table>\n'
    return html


def generate_all_open_ops_table(df_open):
    """Generate HTML table for all open opportunities."""
    # Filter out excluded ops
    df_reportable = df_open[~df_open['Opportunity id'].isin(EXCLUDED_OPS)]

    if len(df_reportable) == 0:
        return "<p><em>No open opportunities found.</em></p>"

    html = '<table class="opportunities-table" style="font-size: 10px;">\n'
    html += '<thead><tr>'
    html += '<th>Opportunity ID</th>'
    html += '<th>Date Created</th>'
    html += '<th>Customer Company Name</th>'
    html += '<th>Partner Project Title</th>'
    html += '<th>Customer Business Problem</th>'
    html += '<th>APN Programs</th>'
    html += '<th>Solution Offered</th>'
    html += '<th>AWS Products</th>'
    html += '<th>Additional Comments</th>'
    html += '<th>Stage</th>'
    html += '<th>Status</th>'
    html += '<th>Est. ARR</th>'
    html += '<th>Delivery Model</th>'
    html += '<th>Use Case</th>'
    html += '<th>Opportunity Type</th>'
    html += '<th>AWS Sales Rep Name</th>'
    html += '<th>Industry Vertical</th>'
    html += '<th>Opportunity Owner Name</th>'
    html += '</tr></thead>\n<tbody>\n'

    for _, row in df_reportable.iterrows():
        html += '<tr>'

        # Opportunity ID
        html += f'<td>{row.get("Opportunity id", "")}</td>'

        # Date Created
        date_created = row.get("Date Created", "")
        if pd.notna(date_created):
            try:
                date_created = pd.to_datetime(date_created, errors='coerce')
                if pd.notna(date_created):
                    date_created = date_created.strftime('%d/%m/%Y')
                else:
                    date_created = ""
            except:
                date_created = ""
        else:
            date_created = ""
        html += f'<td>{date_created}</td>'

        # Customer Company Name
        html += f'<td>{row.get("Customer Company Name", "")}</td>'

        # Partner Project Title
        html += f'<td>{row.get("Partner Project Title", "")}</td>'

        # Customer Business Problem
        problem = str(row.get("Customer Business Problem", ""))
        if problem and problem != 'nan':
            problem = problem[:100] + '...' if len(problem) > 100 else problem
        else:
            problem = ""
        html += f'<td>{problem}</td>'

        # APN Programs
        apn_programs = str(row.get("APN Programs", ""))
        if apn_programs and apn_programs != 'nan':
            apn_programs = apn_programs
        else:
            apn_programs = ""
        html += f'<td>{apn_programs}</td>'

        # Solution Offered
        solution = str(row.get("Solution Offered", ""))
        if solution and solution != 'nan':
            solution = solution[:100] + '...' if len(solution) > 100 else solution
        else:
            solution = ""
        html += f'<td>{solution}</td>'

        # AWS Products
        html += f'<td>{row.get("AWS Products", "")}</td>'

        # Additional Comments
        comments = str(row.get("Additional Comments", ""))
        if comments and comments != 'nan':
            comments = comments[:100] + '...' if len(comments) > 100 else comments
        else:
            comments = ""
        html += f'<td>{comments}</td>'

        # Stage
        html += f'<td>{row.get("Stage", "")}</td>'

        # Status
        html += f'<td>{row.get("Status", "")}</td>'

        # Estimated AWS Monthly Recurring Revenue
        arr = row.get("Estimated AWS Monthly Recurring Revenue", 0)
        if pd.isna(arr):
            arr = 0
        html += f'<td>${arr:,.0f}</td>'

        # Delivery Model
        html += f'<td>{row.get("Delivery Model", "")}</td>'

        # Use Case
        html += f'<td>{row.get("Use Case", "")}</td>'

        # Opportunity Type
        html += f'<td>{row.get("Opportunity Type", "")}</td>'

        # AWS Sales Rep Name
        html += f'<td>{row.get("AWS Sales Rep Name", "")}</td>'

        # Industry Vertical
        html += f'<td>{row.get("Industry Vertical", "")}</td>'

        # Opportunity Owner Name
        html += f'<td>{row.get("Opportunity Owner Name", "")}</td>'

        html += '</tr>\n'

    html += '</tbody></table>\n'
    return html


def generate_email_html(df_stale, df_open, current_stats, previous_stats=None, comparison_data=None):
    """
    Generate complete HTML email body.

    Args:
        df_stale: DataFrame with stale opportunities
        df_open: DataFrame with all open opportunities
        current_stats: Current week stats dict
        previous_stats: Previous week stats dict (optional)
        comparison_data: Comparison data dict (optional

    Returns:
        HTML string for email body
    """
    # ULTRA LOGGING - Function entry
    print("\n" + "🔥" * 60)
    print("[EMAIL_GENERATOR] generate_email_html() CALLED - FUNCTION ENTRY")
    print(f"[EMAIL_GENERATOR] df_open type: {type(df_open)}")
    print(f"[EMAIL_GENERATOR] df_open shape: {df_open.shape}")
    print(f"[EMAIL_GENERATOR] df_open columns: {df_open.columns.tolist()}")
    print(f"[EMAIL_GENERATOR] Total opportunities in df_open: {len(df_open)}")
    print(f"[EMAIL_GENERATOR] df_open['Opportunity id'] unique count: {df_open['Opportunity id'].nunique()}")

    # CRITICAL: Log comparison parameters
    print("\n" + "📊" * 60)
    print("[EMAIL_GENERATOR] *** COMPARISON PARAMETERS CHECK ***")
    print(f"[EMAIL_GENERATOR] previous_stats provided: {previous_stats is not None}")
    if previous_stats:
        print(f"[EMAIL_GENERATOR] previous_stats type: {type(previous_stats)}")
        print(f"[EMAIL_GENERATOR] previous_stats keys: {list(previous_stats.keys()) if isinstance(previous_stats, dict) else 'NOT A DICT'}")
        print(f"[EMAIL_GENERATOR] previous_stats: {previous_stats}")

    print(f"\n[EMAIL_GENERATOR] comparison_data provided: {comparison_data is not None}")
    if comparison_data:
        print(f"[EMAIL_GENERATOR] comparison_data type: {type(comparison_data)}")
        print(f"[EMAIL_GENERATOR] comparison_data keys: {list(comparison_data.keys()) if isinstance(comparison_data, dict) else 'NOT A DICT'}")
        if isinstance(comparison_data, dict):
            print(f"[EMAIL_GENERATOR] new_ops count: {len(comparison_data.get('new_ops', []))}")
            print(f"[EMAIL_GENERATOR] closed_ops count: {len(comparison_data.get('closed_ops', []))}")
            print(f"[EMAIL_GENERATOR] status_changes count: {len(comparison_data.get('status_changes', []))}")
    print("📊" * 60 + "\n")

    print("🔥" * 60 + "\n")

    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {
            font-family: Arial, sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #000000;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        h1 {
            color: #0078D4;
            border-bottom: 3px solid #0078D4;
            padding-bottom: 10px;
        }
        h2 {
            color: #333;
            margin-top: 30px;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 5px;
        }
        h3 {
            color: #666;
            margin-top: 20px;
        }
        .summary-section {
            background-color: #f5f5f5;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-top: 15px;
        }
        .stat-box {
            background-color: white;
            padding: 15px;
            border-radius: 6px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .stat-label {
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .stat-value {
            font-size: 28px;
            font-weight: bold;
            color: #0078D4;
            margin: 10px 0;
        }
        .stat-prev {
            font-size: 11px;
            color: #999;
        }
        .changes-section {
            margin: 30px 0;
        }
        table.opportunities-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        table.opportunities-table th {
            background-color: #0078D4;
            color: white;
            text-align: left;
            padding: 12px 8px;
            font-weight: bold;
        }
        table.opportunities-table td {
            padding: 10px 8px;
            border: 1px solid #ddd;
        }
        table.opportunities-table tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        table.opportunities-table tr:hover {
            background-color: #f0f0f0;
        }
        ul {
            list-style-type: none;
            padding-left: 0;
        }
        ul li {
            padding: 5px 0;
            border-bottom: 1px solid #e0e0e0;
        }
        ul li:last-child {
            border-bottom: none;
        }
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid #e0e0e0;
            font-size: 10pt;
            color: #666;
        }
    </style>
</head>
<body>
"""

    # Intro message with dynamic Bedrock-generated content
    print("=" * 100)
    print("[EMAIL_GENERATOR] ABOUT TO CALL BEDROCK")
    print(f"[EMAIL_GENERATOR] current_stats keys: {list(current_stats.keys())}")
    print(f"[EMAIL_GENERATOR] current_stats: {current_stats}")
    print(f"[EMAIL_GENERATOR] WA count in current_stats: {current_stats.get('well_architected_count', 'NOT FOUND')}")
    print(f"[EMAIL_GENERATOR] RAPID count in current_stats: {current_stats.get('rapid_pilot_count', 'NOT FOUND')}")
    print("=" * 100)
    dynamic_intro = generate_intro_message(current_stats, previous_stats, comparison_data)
    print("=" * 100)
    print("[EMAIL_GENERATOR] BEDROCK RETURNED")
    print(f"[EMAIL_GENERATOR] dynamic_intro: {dynamic_intro}")
    print("=" * 100)

    html += '<div style="background-color: #e7f3ff; padding: 15px; border-left: 4px solid #0078D4; margin: 20px 0; border-radius: 4px;">\n'
    html += '<p><strong>Hi All,</strong></p>\n'
    html += f'<p>{dynamic_intro}</p>\n'
    html += '</div>\n'

    # ACE Hygiene Importance message (separate blue box)
    html += '<div style="background-color: #e7f3ff; padding: 15px; border-left: 4px solid #0078D4; margin: 20px 0; border-radius: 4px;">\n'
    html += '<p><strong>Keep your ACE hygiene tight — it matters.</strong><br>'
    html += 'Detailed, accurate, and regularly updated ACE opportunities directly improve our AWS Co-Sell score, '
    html += 'making us more visible to AWS sellers. Good data = higher score = more co-sell leads.</p>\n'
    html += '</div>\n'

    # Summary section (moved here - right after ACE Hygiene message)
    html += generate_summary_section(current_stats, previous_stats)

    # Ambassador tagging reminder
    html += '<div style="background-color: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0; border-radius: 4px;">\n'
    html += '<p style="margin: 0;"><strong>📝 Reminder:</strong> Please tag <code>#Ambassador:jason.oliver@colibridigital.io</code> '
    html += 'in the <strong>Additional Comments</strong> field of ACE for all opportunities.</p>\n'
    html += '</div>\n'

    # AWS Account ID reminder (CRITICAL for LARR tracking)
    html += '<div style="background-color: #ffebee; padding: 15px; border-left: 4px solid #d32f2f; margin: 20px 0; border-radius: 4px;">\n'
    html += '<p style="margin: 0;"><strong>🚨 CRITICAL: AWS Account ID Required</strong><br>'
    html += 'Before moving any opportunity to <strong>Launched</strong>, you MUST add the <strong>AWS Account ID</strong>. '
    html += 'Without this ID, the opportunity will NOT count toward our <strong>LARR (Launched Annual Recurring Revenue)</strong> metrics. '
    html += 'This significantly impacts our AWS partnership score and co-sell opportunities. Add the AWS Account ID as soon as possible for all opportunities.</p>\n'
    html += '</div>\n'

    # Feedback section
    html += '<div style="background-color: #f0f8ff; padding: 15px; border-left: 4px solid #0078D4; margin: 20px 0; border-radius: 4px;">\n'
    html += '<p style="margin: 0;"><strong>📢 Feedback Welcome!</strong><br>'
    html += 'Have suggestions to improve this report? Notice any errors or issues? Please let me know! '
    html += 'Your feedback helps make this report more useful for everyone.</p>\n'
    html += '</div>\n'

    # Key Insights section
    html += generate_insights_section(df_open)

    # ACE Hygiene Report title and date (moved here - before Stale Opportunities)
    html += '<h1>ACE Hygiene Report - New Format</h1>\n'
    html += f'<p>Report generated: {current_stats["processed_date"].strftime("%d %B %Y")}</p>\n'

    # Stale opportunities section (moved above Changes section)
    df_stale_reportable = df_stale[~df_stale['Opportunity id'].isin(EXCLUDED_OPS)]
    html += '<div class="stale-section">\n'
    html += '<h2>⚠️ Stale Opportunities (30+ Days Since Last Update)</h2>\n'
    if len(df_stale_reportable) > 0:
        html += f'<p>The following <strong>{len(df_stale_reportable)} opportunities</strong> need to be updated to maintain our Partner Central score:</p>\n'
    else:
        html += '<p>Great news! No opportunities have been stale for more than 30 days.</p>\n'
    html += generate_stale_ops_table(df_stale)
    html += '</div>\n'

    # Changes section (if comparison available) - moved below Stale Opportunities
    if comparison_data:
        html += generate_changes_section(comparison_data)

    # All Open Ops summary section (moved to bottom, just above signature)
    df_open_reportable = df_open[~df_open['Opportunity id'].isin(EXCLUDED_OPS)]
    html += '<div class="all-ops-section">\n'
    html += '<h2>📋 All Open Opportunities in ACE</h2>\n'
    html += '<p>Please update these opportunities in Partner Central or let me know if they should be closed.</p>\n'
    html += f'<p>Complete list of all <strong>{len(df_open_reportable)} current open opportunities</strong> in Partner Central ACE:</p>\n'
    html += generate_all_open_ops_table(df_open)
    html += '</div>\n'

    html += '<div class="footer">'
    html += '<p>Many thanks,<br>Gianluca</p>'
    html += '</div>'

    html += '</body></html>'

    return html


def create_email_message(df_stale, df_open, current_stats, previous_stats=None, comparison_data=None,
                        to_addresses=None, cc_addresses=None):
    """Create email message with HTML content."""
    if to_addresses is None:
        to_addresses = EMAIL_CONFIG['to']
    if cc_addresses is None:
        cc_addresses = EMAIL_CONFIG['cc']

    print(f"[EMAIL DEBUG] Creating email message:")
    print(f"[EMAIL DEBUG] TO: {to_addresses}")
    print(f"[EMAIL DEBUG] CC: {cc_addresses}")

    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = EMAIL_CONFIG['subject']
    msg['From'] = f"{EMAIL_CONFIG['from_name']} <{EMAIL_CONFIG['from_email']}>"
    msg['To'] = ', '.join(to_addresses)
    if cc_addresses:
        msg['Cc'] = ', '.join(cc_addresses)
        print(f"[EMAIL DEBUG] Adding CC header: {msg['Cc']}")
    else:
        print(f"[EMAIL DEBUG] No CC recipients")

    print(f"[EMAIL DEBUG] TO header: {msg['To']}")

    # Generate HTML body
    html_content = generate_email_html(df_stale, df_open, current_stats, previous_stats, comparison_data)

    # Attach HTML content
    html_part = MIMEText(html_content, 'html')
    msg.attach(html_part)

    return msg


def send_email(msg, smtp_password):
    """Send email via SMTP."""
    print("\n" + "="*80)
    print("[SEND_EMAIL] STARTING")
    print("="*80)

    smtp_username = SMTP_CONFIG['username']
    print(f"[SEND_EMAIL] SMTP username: {smtp_username}")
    print(f"[SEND_EMAIL] SMTP server: {SMTP_CONFIG['server']}")
    print(f"[SEND_EMAIL] SMTP port: {SMTP_CONFIG['port']}")
    print(f"[SEND_EMAIL] Use TLS: {SMTP_CONFIG['use_tls']}")
    print(f"[SEND_EMAIL] Password provided: {bool(smtp_password)}")
    if smtp_password:
        print(f"[SEND_EMAIL] Password length BEFORE cleaning: {len(smtp_password)}")
        print(f"[SEND_EMAIL] Password repr BEFORE cleaning: {repr(smtp_password)}")

    if not smtp_password:
        print("[SEND_EMAIL] ERROR: No password provided")
        print("="*80 + "\n")
        return False, "Password is required to send email"

    # CRITICAL: CLEAN PASSWORD - Remove ALL non-ASCII characters and spaces
    print(f"[SEND_EMAIL] ========== CLEANING PASSWORD ==========")
    print(f"[SEND_EMAIL] Original password: {repr(smtp_password)}")
    print(f"[SEND_EMAIL] Original length: {len(smtp_password)}")

    # Check each character
    print(f"[SEND_EMAIL] Character analysis:")
    for i, char in enumerate(smtp_password):
        char_code = ord(char)
        is_ascii = char_code < 128
        is_space = char.isspace()
        print(f"[SEND_EMAIL]   Char {i}: {repr(char)} ord={char_code} ASCII={is_ascii} space={is_space}")

    # Clean it!
    original_password = smtp_password
    smtp_password = ''.join(char for char in smtp_password if ord(char) < 128 and not char.isspace())

    print(f"[SEND_EMAIL] Cleaned password: {repr(smtp_password)}")
    print(f"[SEND_EMAIL] Cleaned length: {len(smtp_password)}")
    print(f"[SEND_EMAIL] Removed {len(original_password) - len(smtp_password)} characters")

    if len(smtp_password) != 16:
        print(f"[SEND_EMAIL] ⚠️  WARNING: Gmail App Passwords should be 16 characters, got {len(smtp_password)}")

    print(f"[SEND_EMAIL] ==========================================")

    print(f"[SEND_EMAIL] Message headers:")
    print(f"[SEND_EMAIL]   Subject: {msg.get('Subject', 'N/A')}")
    print(f"[SEND_EMAIL]   From: {msg.get('From', 'N/A')}")
    print(f"[SEND_EMAIL]   To: {msg.get('To', 'N/A')}")
    print(f"[SEND_EMAIL]   Cc: {msg.get('Cc', 'N/A')}")

    try:
        print(f"[SEND_EMAIL] Creating SMTP connection...")
        server = smtplib.SMTP(SMTP_CONFIG['server'], SMTP_CONFIG['port'])
        print(f"[SEND_EMAIL] SMTP connection created successfully")

        print(f"[SEND_EMAIL] Setting debug level to 2...")
        server.set_debuglevel(2)
        print(f"[SEND_EMAIL] Debug level set")

        if SMTP_CONFIG['use_tls']:
            print(f"[SEND_EMAIL] Starting TLS...")
            server.starttls()
            print(f"[SEND_EMAIL] TLS started successfully")

        print(f"[SEND_EMAIL] ========== ATTEMPTING LOGIN ==========")
        print(f"[SEND_EMAIL] Username: {smtp_username}")
        print(f"[SEND_EMAIL] Password: {repr(smtp_password)}")
        print(f"[SEND_EMAIL] Password is ASCII-only: {all(ord(c) < 128 for c in smtp_password)}")
        print(f"[SEND_EMAIL] Calling server.login()...")
        server.login(smtp_username, smtp_password)
        print(f"[SEND_EMAIL] Login successful!")

        # Get all recipients
        print(f"[SEND_EMAIL] Parsing recipients...")
        to_addresses = msg['To'].split(', ')
        print(f"[SEND_EMAIL] TO addresses: {to_addresses}")

        cc_addresses = msg['Cc'].split(', ') if msg['Cc'] else []
        print(f"[SEND_EMAIL] CC addresses: {cc_addresses}")

        all_recipients = to_addresses + cc_addresses
        print(f"[SEND_EMAIL] Total recipients: {len(all_recipients)}")

        print(f"[SEND_EMAIL] Getting message as string for size check...")
        msg_string = msg.as_string()
        print(f"[SEND_EMAIL] Message size: {len(msg_string)} bytes ({len(msg_string)/1024:.1f} KB)")
        print(f"[SEND_EMAIL] Message encoding: {msg_string[:200]}")

        print(f"[SEND_EMAIL] Calling server.send_message()...")
        server.send_message(msg)
        print(f"[SEND_EMAIL] server.send_message() completed!")

        print(f"[SEND_EMAIL] Closing connection...")
        server.quit()
        print(f"[SEND_EMAIL] Connection closed")

        print(f"[SEND_EMAIL] ✅ SUCCESS - Email sent to {len(all_recipients)} recipients")
        print("="*80 + "\n")
        return True, f"Email sent successfully to {len(all_recipients)} recipients"

    except smtplib.SMTPAuthenticationError as e:
        print(f"[SEND_EMAIL] ❌ SMTP AUTH ERROR: {str(e)}")
        import traceback
        print(f"[SEND_EMAIL] TRACEBACK:\n{traceback.format_exc()}")
        print("="*80 + "\n")
        return False, "Authentication failed. Please check your email and password."
    except smtplib.SMTPException as e:
        print(f"[SEND_EMAIL] ❌ SMTP EXCEPTION: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"[SEND_EMAIL] TRACEBACK:\n{traceback.format_exc()}")
        print("="*80 + "\n")
        return False, f"SMTP error occurred: {str(e)}"
    except Exception as e:
        print(f"[SEND_EMAIL] ❌ GENERAL EXCEPTION: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"[SEND_EMAIL] TRACEBACK:\n{traceback.format_exc()}")
        print("="*80 + "\n")
        return False, f"Error sending email: {str(e)}"
