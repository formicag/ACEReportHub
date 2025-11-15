# Save Behavior Analysis - Two Save Mechanisms

**Date**: 2025-11-14
**Analysis**: Comparison of "Save Report" vs "Send to All Recipients" functionality

---

## Summary

✅ **CONFIRMED**: Both buttons save the snapshot to the database

Your understanding is **100% CORRECT**. Here's how each mechanism works:

---

## Mechanism 1: "Save Report (Do NOT Send)" Button

**Route**: `/save_report` (Line 1136 in app.py)
**Button Text**: "💾 Save Report (Do NOT Send)"
**Location**: Visible after clicking "Generate Report" (Image #2)

### Behavior:
1. ✅ **Saves snapshot to database** via `db.save_snapshot()` (Line 1251)
2. ❌ **Does NOT send email**
3. ✅ **Checks for duplicates** - prevents saving same week twice
4. ✅ **Marks session** as `report_saved = True`

### Code Location (app.py:1251-1257):
```python
snapshot_id = db.save_snapshot(
    df_all=df_all,
    snapshot_date=snapshot_date,
    ace_filename=ace_filename,
    ace_file_date=file_date,
    report_week_date=report_week_date
)
```

### What Gets Saved:
- ✅ All opportunity data
- ✅ Snapshot metadata (date, filename, stats)
- ✅ Report week date
- ❌ Email recipients (not passed)
- ❌ Notes about email sent (not included)

---

## Mechanism 2: "Send to All Recipients" Button

**Route**: `/send_email` (Line 665 in app.py)
**Button Text**: "📤 Send to All Recipients"
**Location**: Visible in email preview modal (Image #3)

### Behavior:
1. ✅ **Sends email** to all recipients
2. ✅ **Then saves snapshot to database** (ONLY if email succeeds)
3. ✅ **Saves additional metadata** (email recipients, notes)

### Code Location (app.py:764-772):
```python
# Save snapshot to database
snapshot_id = db.save_snapshot(
    df_all=df_all,
    snapshot_date=datetime.now(),
    ace_filename=session['current_filename'],
    ace_file_date=result['stats']['file_date'],
    email_recipients=EMAIL_CONFIG['to'] + EMAIL_CONFIG['cc'],  # EXTRA
    report_week_date=report_week_date,
    notes=f"Weekly report sent - {session['stats']['stale_ops_count']} stale ops"  # EXTRA
)
```

### What Gets Saved:
- ✅ All opportunity data
- ✅ Snapshot metadata (date, filename, stats)
- ✅ Report week date
- ✅ **Email recipients** (who received the email)
- ✅ **Notes** (e.g., "Weekly report sent - 1 stale ops")

---

## Key Differences

| Aspect | Save Report (No Send) | Send to All Recipients |
|--------|----------------------|------------------------|
| **Saves to DB?** | ✅ Yes | ✅ Yes |
| **Sends Email?** | ❌ No | ✅ Yes |
| **When Saves?** | Immediately | After email succeeds |
| **Email Recipients** | Not saved | Saved in DB |
| **Notes Field** | Not saved | Saved (e.g., "sent - X stale") |
| **Requires Password?** | ❌ No | ✅ Yes |
| **Duplicate Check?** | ✅ Yes | ❌ No (assumes unique) |

---

## Workflow Comparison

### Workflow 1: Save Without Sending
```
Upload File → Generate Report → Save Report (No Send)
                              ↓
                         Snapshot saved to DB
                         (No email sent)
```

**Use Case**:
- Preview data before sending
- Save weekly data for records without emailing
- Test imports without notifying team

---

### Workflow 2: Save and Send
```
Upload File → Generate Report → Preview Email → Send to All
                              ↓                    ↓
                         HTML generated    Email sent → Snapshot saved to DB
```

**Use Case**:
- Standard weekly workflow
- Send report and automatically save to database
- Track which recipients received the email

---

## Important Notes

### 1. Both Save the Snapshot ✅
**YES** - Both buttons call `db.save_snapshot()` and create a new entry in the database.

### 2. Duplicate Protection
- **"Save Report"**: Checks for duplicates, prevents saving same week twice (Line 1180)
- **"Send to All"**: No duplicate check (assumes you wouldn't send twice)

### 3. Email Metadata
Only "Send to All Recipients" saves:
- Who received the email
- Notes about the report (stale count, etc.)

### 4. Timing
- **"Save Report"**: Saves immediately when you click
- **"Send to All"**: Saves ONLY AFTER email succeeds (Line 752)
  - If email fails, snapshot is NOT saved
  - This prevents having "saved" reports that weren't actually sent

---

## Historical Context (Your Original Implementation)

Based on the code, here's what Claude Code originally built:

### Phase 1: Original Implementation
- **Only** "Send to All Recipients" existed
- Saved snapshot ONLY when email was sent
- No way to save without emailing

### Phase 2: Your Request
- You asked for ability to save WITHOUT sending
- Claude Code added `/save_report` route
- Added "Save Report (Do NOT Send)" button
- Both now save to database

---

## Verification with Your Screenshots

### Image #1: Dashboard
Shows "Last Report" with Snapshot #4 data:
- Sent Date: 2025-11-07
- Total Open Ops: 54
- Avg Days: 15.4
- Stale Ops: 1

This snapshot was saved to the database (either via "Save Report" OR "Send to All").

### Image #2: After Upload
Shows two buttons:
- "👁️ Preview Email" - Just shows preview, no save
- "💾 Save Report (Do NOT Send)" - **Saves to DB without emailing**

### Image #3: Email Preview Modal
Shows one button:
- "📤 Send to All Recipients" - **Sends email AND saves to DB**

---

## Current Database State

Based on your dashboard showing 3 snapshots:
- Snapshot #1: Baseline (protected)
- Snapshot #2: Could be from either button
- Snapshot #4: Could be from either button

You can check which ones have email recipient data:
```sql
SELECT snapshot_id, email_sent_to FROM weekly_snapshots;
```

- If `email_sent_to` is NULL: Saved via "Save Report (No Send)"
- If `email_sent_to` has data: Saved via "Send to All Recipients"

---

## Conclusion

✅ **Your Understanding is CORRECT**

Both buttons save snapshots to the database:
1. **"Save Report (Do NOT Send)"** - Saves without emailing
2. **"Send to All Recipients"** - Sends email, then saves

The key difference is:
- **What**: Both save to DB
- **When**: One saves immediately, other saves after email succeeds
- **Extra Data**: "Send to All" also saves email recipients and notes

---

**Analysis Completed**: 2025-11-14
**Result**: ✅ Both mechanisms save to database as intended
