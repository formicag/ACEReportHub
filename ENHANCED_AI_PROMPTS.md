# Enhanced AI Prompts - ARR Analysis & Opportunity Context

**Date**: 2025-11-14
**Enhancement**: Added ARR analysis and opportunity context to Bedrock AI intro generation
**Status**: ✅ DEPLOYED

**Latest Update**: 2025-11-15 - Fixed duplicate "Great news!" message in email preview
**Status**: ✅ DEPLOYED

---

## Summary

Enhanced the AWS Bedrock Claude prompt to:
1. Analyze ARR changes week-over-week
2. Identify top new opportunities driving ARR increases
3. Include customer, seller, and use case context
4. Use reserved professional tone (not overly enthusiastic)

---

## What Changed

### **File Modified**: `bedrock_client.py`

### **Changes Made**:

1. **ARR Analysis** (Lines 31, 46-55):
   ```python
   current_arr = current_stats.get('total_arr', 0)
   prev_arr = previous_stats.get('total_arr', 0)
   arr_delta = current_arr - prev_arr
   arr_pct_change = (arr_delta / prev_arr) * 100 if prev_arr > 0 else 0
   ```

2. **Top Opportunity Extraction** (Lines 69-86):
   ```python
   if arr_delta > 100000:  # $100k threshold
       # Find top new opportunity by ARR
       new_ops_sorted = new_ops_df.sort_values(
           by='Estimated AWS Monthly Recurring Revenue',
           ascending=False
       )
       top_new_opportunity = {
           'customer': top_op['Customer Company Name'],
           'arr': top_op['Estimated AWS Monthly Recurring Revenue'],
           'seller': top_op['Created By'],
           'title': top_op['Partner Project Title'],
           'problem': top_op['Customer Business Problem'][:100]
       }
   ```

3. **Enhanced Context** (Lines 100-126):
   ```python
   context = f"""
   ARR Analysis:
   Current ARR: ${current_arr:,.0f}
   Previous ARR: ${prev_arr:,.0f}
   ARR change: ${arr_delta:,.0f} ({arr_pct_change:.1f}%)

   Notable New Opportunity (driving ARR increase):
   - Customer: {customer}
   - ARR: ${arr:,.0f}
   - Seller: {seller}
   - Project: {title}
   - Context: {problem}
   ```

4. **Reserved Professional Tone** (Lines 154-159):
   ```
   TONE - RESERVED PROFESSIONAL:
   - Use: "Notable", "Significant progress", "Good improvement"
   - Avoid: "Excellent!", "Amazing!", "Fantastic!", "Great!"
   - Be factual, not promotional
   - State facts, don't cheerlead
   ```

---

## How It Works Now

### **Trigger Conditions**:

**If ARR increase > $100k**:
- AI analyzes new opportunities
- Identifies highest-value new opportunity
- Includes in intro message

**Example Context Sent to Bedrock**:
```
Current stale opportunities: 0
Previous week stale opportunities: 1
Consecutive weeks with zero stale: 1
Trend: improving
Total open opportunities: 38

ARR Analysis:
Current ARR: $929,301
Previous ARR: $126,536
ARR change: $802,765 (634.4%)

Notable New Opportunity (driving ARR increase):
- Customer: Capita Plc
- ARR: $800,000
- Seller: Alan Rowden
- Project: Capita Trace and Data Solution
- Context: Customer looking to replace ageing process heavy solution that is damaging margin and SLAs

Well-Architected opportunities: 6
RAPID PILOT opportunities: 0
```

---

## Expected Output

### **Old AI Output** (Before Enhancement):
```
Hi All,

Well done! No stale opportunities this week - 100% success! This represents
good progress from last week's single stale opportunity, marking our first
consecutive week at zero. Our pipeline includes 6 Well-Architected opportunities
among the 38 total open opportunities.
```

**Missing**: No mention of the massive $803k ARR increase or the Capita opportunity!

---

### **New AI Output** (After Enhancement):
```
Well done! No stale opportunities this week - 100% success! This marks our
first consecutive week at zero, showing good progress from last week.

Notable this week: Pipeline ARR increased by $803k, primarily driven by a new
$800k Capita opportunity (Capita Trace and Data Solution) added by Alan Rowden.
Our pipeline includes 6 Well-Architected opportunities among 38 total open
opportunities.
```

**Improved**:
- ✅ Mentions the $803k ARR increase
- ✅ Credits Alan Rowden (seller)
- ✅ Includes customer (Capita) and project name
- ✅ Reserved professional tone
- ✅ Concise and factual

---

## Tone Comparison

### **Before** (Too Enthusiastic):
- "Excellent progress!"
- "Amazing improvement!"
- "Fantastic work team!"
- "Outstanding performance!"

### **After** (Reserved Professional):
- "Notable this week"
- "Good progress"
- "Marks our first consecutive week"
- "Significant improvement"

---

## Thresholds & Logic

### **ARR Increase Threshold**: $100,000

**Why $100k?**
- Filters out small changes
- Focuses on meaningful business impact
- Prevents noise from minor ARR fluctuations

### **Top Opportunity Selection**:
- Sorts new opportunities by ARR (descending)
- Takes highest value opportunity
- Extracts: Customer, ARR, Seller, Project, Use Case

---

## What Gets Included in Intro

### **Priority Order**:

1. **Stale Ops Status** (Always included)
   - 0 stale: "Well done! No stale opportunities this week"
   - >0 stale: "[X] stale opportunities need updating"
   - Consecutive weeks: "This marks our [X] consecutive week(s) at zero"

2. **ARR Analysis** (If increase >$100k)
   - "Notable this week: Pipeline ARR increased by $[amount]"
   - "primarily driven by a new $[arr] [Customer] opportunity ([Project]) added by [Seller]"

3. **Pipeline Composition** (Always included)
   - Total open opportunities
   - Well-Architected count (if > 0)
   - RAPID PILOT count (if > 0)

---

## Examples

### **Example 1: Large ARR Increase (This Week)**

**Input**:
- ARR: $126k → $929k (+$803k)
- New op: Capita Plc, $800k (Alan Rowden)

**Output**:
```
Well done! No stale opportunities this week - 100% success! This marks our
first consecutive week at zero.

Notable this week: Pipeline ARR increased by $803k, primarily driven by a new
$800k Capita opportunity (Capita Trace and Data Solution) added by Alan Rowden.
Our pipeline includes 6 Well-Architected opportunities among 38 total open
opportunities.
```

---

### **Example 2: Small ARR Change (No Mention)**

**Input**:
- ARR: $500k → $520k (+$20k)
- Below $100k threshold

**Output**:
```
Well done! No stale opportunities this week - 100% success! This marks our
first consecutive week at zero. Our pipeline includes 6 Well-Architected
opportunities among 38 total open opportunities.
```

**ARR change NOT mentioned** (below threshold)

---

### **Example 3: Stale Ops Present**

**Input**:
- Stale ops: 5
- ARR: +$150k
- New op: ABC Corp, $150k (John Doe)

**Output**:
```
We have 5 stale opportunities that need updating (detailed further down in the
report) to reach 100% hygiene.

Notable this week: Pipeline ARR increased by $150k, primarily driven by a new
$150k ABC Corp opportunity (Cloud Migration) added by John Doe. Our pipeline
includes 6 Well-Architected opportunities among 38 total open opportunities.
```

---

## Benefits

### **1. Business Intelligence** 📊
- Highlights what's driving pipeline changes
- Surfaces high-value opportunities immediately
- Recognizes seller contributions

### **2. Actionable Insights** 🎯
- Stakeholders know WHY ARR changed
- Can follow up on big opportunities
- Tracks seller performance

### **3. Professional Tone** 🎓
- Reserved, not overly enthusiastic
- Factual, data-driven
- Appropriate for executive audience

### **4. Context-Aware** 🧠
- AI analyzes data before writing
- Adapts message to what changed
- Only mentions notable changes

---

## Testing

### **Test Scenario 1: Your Current Data**

Upload Export_14.xlsx and check if intro mentions:
- ✅ "Pipeline ARR increased by $803k"
- ✅ "$800k Capita opportunity"
- ✅ "Alan Rowden"

### **Test Scenario 2: Next Week (No Big Change)**

If next week ARR change < $100k:
- ✅ Should NOT mention ARR
- ✅ Should still mention stale status
- ✅ Should mention WA/RAPID counts

### **Test Scenario 3: Multiple Big Opportunities**

If multiple new ops > $100k:
- ✅ Should mention HIGHEST value opportunity only
- ✅ Should include seller name
- ✅ Should keep message concise

---

## Consecutive Weeks Counter

**Already Working** ✅ (No changes needed)

**How it works**:
- Stored in `weekly_snapshots.consecutive_weeks_no_stale` column
- Increments if current week AND previous week have 0 stale
- Resets to 0 if any stale ops
- Resets to 1 if 0 stale this week BUT stale ops last week

**Next Week**:
- If 0 stale again: "This marks our 2 consecutive weeks at zero"
- If stale appears: Resets to 0

---

## Future Enhancements (Ideas)

### **Potential Additions**:

1. **Launched Ops Recognition**:
   - If >5 ops launched: "Notable activity: 7 opportunities moved to Launched this week"
   - Could mention top launcher by count

2. **Well-Architected Highlights**:
   - If WA count increased significantly: "WA pipeline grew by 3 opportunities"

3. **Stale Trend Analysis**:
   - "Stale count decreased from 10 to 5 - good progress toward 100% hygiene"

4. **Custom Thresholds**:
   - Make $100k threshold configurable
   - Adjust based on typical ARR ranges

---

## Rollback

If the enhanced AI doesn't work as expected:

**Quick Revert**:
```bash
git checkout bedrock_client.py
python3 app.py
```

Or manually:
1. Remove ARR analysis logic (lines 46-55)
2. Remove opportunity extraction (lines 69-86)
3. Restore old prompt (remove ARR sections)

---

## Summary

✅ **Enhanced AI** with ARR analysis and opportunity context
✅ **Reserved professional tone** (no over-enthusiasm)
✅ **Data-driven insights** (highlights what matters)
✅ **Consecutive weeks** counter already working
✅ **Ready for tonight's report**

**Your $800k Capita opportunity will now be highlighted in the intro!** 🎯

---

**Implementation Date**: 2025-11-14
**Status**: ✅ DEPLOYED
**Flask**: Running at http://localhost:5001
**Next Step**: Test with tonight's report!

---

## Latest Fix - 2025-11-15

### **Duplicate "Great news!" Message**

**Issue**: In email preview, the message "Great news! No opportunities have been stale for more than 30 days." appeared twice.

**Root Cause**:
- **Line 377** in `email_generator.py`: `generate_stale_ops_table()` function returns this message
- **Line 761** in `email_generator.py`: Main email generation also added the same message before calling the function

**Fix Applied**:
```python
# BEFORE (Lines 760-761):
else:
    html += '<p>Great news! No opportunities have been stale for more than 30 days.</p>\n'
html += generate_stale_ops_table(df_stale)

# AFTER (Lines 760-761):
# REMOVED duplicate "Great news!" message - already handled by generate_stale_ops_table() function
html += generate_stale_ops_table(df_stale)
```

**Result**: ✅ Message now appears only once (from the function), eliminating duplication

**File Modified**: `email_generator.py` (removed lines 760-761)

**Status**: ✅ DEPLOYED
