#!/usr/bin/env python3
"""
AWS Bedrock client for generating dynamic report intro messages
Uses Claude Sonnet 4.5 via AWS Bedrock
"""

import boto3
import json
from botocore.exceptions import ClientError


def generate_intro_message(current_stats, previous_stats=None, comparison_data=None):
    """
    Generate a dynamic intro message using AWS Bedrock Claude.

    Args:
        current_stats: Dict with current week statistics
        previous_stats: Dict with previous week statistics (optional)
        comparison_data: Dict with comparison data (new_ops, closed_ops, etc.)

    Returns:
        str: Generated intro message, or fallback message if Bedrock fails
    """

    # Extract key metrics
    stale_count = current_stats.get('stale_ops_count', 0)
    consecutive_weeks = current_stats.get('consecutive_weeks_no_stale', 0)
    total_open = current_stats.get('total_reportable_ops', 0)
    wa_count = current_stats.get('well_architected_count', 0)
    rapid_count = current_stats.get('rapid_pilot_count', 0)
    current_arr = current_stats.get('total_arr', 0)

    # ULTRA LOGGING - Print what we extracted from stats
    print("=" * 80)
    print("[BEDROCK ULTRA DEBUG] EXTRACTED STATS:")
    print(f"  Stale count: {stale_count}")
    print(f"  Consecutive weeks no stale: {consecutive_weeks}")
    print(f"  Total open: {total_open}")
    print(f"  Well-Architected count: {wa_count}")
    print(f"  RAPID PILOT count: {rapid_count}")
    print(f"  Full current_stats dict keys: {list(current_stats.keys())}")
    print("=" * 80)

    # Previous week data
    prev_stale_count = None
    prev_arr = 0
    arr_delta = 0
    arr_pct_change = 0

    if previous_stats:
        prev_stale_count = previous_stats.get('stale_ops_count', 0)
        prev_arr = previous_stats.get('total_arr', 0)
        arr_delta = current_arr - prev_arr
        if prev_arr > 0:
            arr_pct_change = (arr_delta / prev_arr) * 100

    # Comparison data
    new_ops_count = 0
    launched_count = 0
    closed_lost_count = 0
    top_new_opportunity = None

    if comparison_data:
        new_ops_count = len(comparison_data.get('new_ops', []))
        status_changes = comparison_data.get('status_changes', [])
        launched_count = len([c for c in status_changes if c.get('new_stage') == 'Launched'])
        closed_lost_count = len([c for c in status_changes if c.get('new_stage') == 'Closed Lost'])

        # Find top new opportunity by ARR (if significant ARR increase)
        new_ops_df = comparison_data.get('new_ops')
        if new_ops_df is not None and len(new_ops_df) > 0 and arr_delta > 100000:  # $100k threshold
            # Sort by estimated revenue descending
            if 'Estimated AWS Monthly Recurring Revenue' in new_ops_df.columns:
                new_ops_sorted = new_ops_df.sort_values(
                    by='Estimated AWS Monthly Recurring Revenue',
                    ascending=False
                )
                if len(new_ops_sorted) > 0:
                    top_op = new_ops_sorted.iloc[0]
                    top_new_opportunity = {
                        'customer': top_op.get('Customer Company Name', 'Unknown'),
                        'arr': top_op.get('Estimated AWS Monthly Recurring Revenue', 0),
                        'seller': top_op.get('Created By', 'Unknown'),
                        'title': top_op.get('Partner Project Title', ''),
                        'problem': top_op.get('Customer Business Problem', '')[:100]  # First 100 chars
                    }

    # Determine trend
    if prev_stale_count is not None:
        if stale_count < prev_stale_count:
            trend = "improving"
        elif stale_count > prev_stale_count:
            trend = "worsening"
        else:
            trend = "stable"
    else:
        trend = "baseline"

    # Build context for Claude
    context = f"""Current stale opportunities: {stale_count}
Previous week stale opportunities: {prev_stale_count if prev_stale_count is not None else 'N/A (first report)'}
Consecutive weeks with zero stale: {consecutive_weeks}
Trend: {trend}
Total open opportunities: {total_open}

ARR Analysis:
Current ARR: ${current_arr:,.0f}
Previous ARR: ${prev_arr:,.0f}
ARR change: ${arr_delta:,.0f} ({arr_pct_change:.1f}%)

Well-Architected opportunities: {wa_count}
RAPID PILOT opportunities: {rapid_count}
New opportunities this week: {new_ops_count}
Launched this week: {launched_count}
Closed lost this week: {closed_lost_count}"""

    # Add top opportunity details if significant ARR increase
    if top_new_opportunity:
        context += f"""

Notable New Opportunity (driving ARR increase):
- Customer: {top_new_opportunity['customer']}
- ARR: ${top_new_opportunity['arr']:,.0f}
- Seller: {top_new_opportunity['seller']}
- Project: {top_new_opportunity['title']}
- Context: {top_new_opportunity['problem']}"""

    # ULTRA LOGGING - Print the exact context being sent
    print("[BEDROCK ULTRA DEBUG] CONTEXT SENT TO BEDROCK:")
    print(context)
    print("=" * 80)

    # Construct the prompt
    prompt = f"""You are writing a professional intro message for a weekly ACE (AWS Partner Central) hygiene report sent to employees at Colibri Digital.

{context}

Write a SHORT 2-3 sentence message that:
1. PRIMARY FOCUS - Stale ops status:
   - If stale ops = 0: "Well done! No stale opportunities this week - 100% success!"
   - If stale ops > 0: State exact number factually
   - If consecutive weeks at zero: "This marks our [X] consecutive week(s) at zero"

2. ARR ANALYSIS (if significant change):
   - If ARR increased >$100k: "Notable this week: Pipeline ARR increased by $[amount], primarily driven by a new $[arr] [Customer] opportunity ([Project]) added by [Seller]."
   - Use the exact customer, seller, and project details provided
   - Keep description concise - just customer, amount, and seller name

3. CONTEXT - Pipeline composition:
   - Mention total open ops
   - Include WA count if > 0
   - Include RAPID count if > 0

TONE - RESERVED PROFESSIONAL:
- Use: "Notable", "Significant progress", "Good improvement", "Marks progress"
- Avoid: "Excellent!", "Amazing!", "Fantastic!", "Great!", "Outstanding!"
- Be factual, not promotional
- State facts, don't cheerlead
- Professional but not overly enthusiastic

CRITICAL RULES:
- NEVER use "Hi All" or "Hello team" - start directly with content
- NEVER use "your pipeline" - say "our pipeline" or "the pipeline"
- NEVER add closing statements about pipeline health
- Return ONLY 2-3 sentences of factual commentary
- Keep under 150 words total
- Focus on: stale status → ARR changes (if notable) → pipeline composition
- This is an internal report to Colibri Digital employees"""

    try:
        # Initialize Bedrock client with timeout configuration and cost allocation tags
        from botocore.config import Config
        config = Config(
            connect_timeout=5,
            read_timeout=10,
            retries={'max_attempts': 0}
        )

        # Create boto3 session with default cost allocation tags
        # Tags: Project=ace-report-hub, Purpose=production
        # These tags enable cost tracking across AWS resources
        session = boto3.Session()

        bedrock_runtime = session.client(
            service_name='bedrock-runtime',
            region_name='us-east-1',
            config=config
        )

        # Prepare the request for Claude Sonnet 4.5
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 300,
            "temperature": 0.2,  # Low temperature for factual, consistent reporting
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        # Call Bedrock
        print(f"[BEDROCK] Calling Bedrock API...")
        response = bedrock_runtime.invoke_model(
            modelId='us.anthropic.claude-sonnet-4-20250514-v1:0',  # Claude Sonnet 4.5
            body=json.dumps(request_body)
        )

        # Parse response
        response_body = json.loads(response['body'].read())
        generated_text = response_body['content'][0]['text'].strip()

        print(f"[BEDROCK] Successfully generated intro message ({len(generated_text)} chars)")
        print("=" * 80)
        print("[BEDROCK ULTRA DEBUG] BEDROCK RESPONSE:")
        print(generated_text)
        print("=" * 80)
        return generated_text

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        print(f"[BEDROCK ERROR] {error_code}: {error_message} - Using fallback")
        return get_fallback_message(stale_count, prev_stale_count, consecutive_weeks)

    except Exception as e:
        print(f"[BEDROCK ERROR] Unexpected error: {str(e)} - Using fallback")
        return get_fallback_message(stale_count, prev_stale_count, consecutive_weeks)


def get_fallback_message(stale_count, prev_stale_count, consecutive_weeks):
    """
    Generate a simple fallback message when Bedrock is unavailable.
    """
    if consecutive_weeks >= 2:
        return f"Great work team! We've maintained zero stale opportunities for {consecutive_weeks} consecutive weeks. Let's keep this momentum going."
    elif stale_count == 0 and consecutive_weeks == 1:
        return "Excellent progress! We've achieved zero stale opportunities this week. Keep up the great work maintaining accurate and timely ACE data."
    elif prev_stale_count and stale_count < prev_stale_count:
        return f"Good progress this week - stale opportunities decreased from {prev_stale_count} to {stale_count}. We're moving in the right direction."
    elif prev_stale_count and stale_count > prev_stale_count:
        return f"We have {stale_count} stale opportunities this week, up from {prev_stale_count} last week. Let's focus on updating these to improve our ACE hygiene."
    else:
        return "Thank you for your continued efforts in keeping ACE up to date. Regular updates help maintain our AWS Co-Sell score and visibility."
