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
    if previous_stats:
        prev_stale_count = previous_stats.get('stale_ops_count', 0)

    # Comparison data
    new_ops_count = 0
    launched_count = 0
    closed_lost_count = 0

    if comparison_data:
        new_ops_count = len(comparison_data.get('new_ops', []))
        status_changes = comparison_data.get('status_changes', [])
        launched_count = len([c for c in status_changes if c.get('new_stage') == 'Launched'])
        closed_lost_count = len([c for c in status_changes if c.get('new_stage') == 'Closed Lost'])

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
Well-Architected opportunities: {wa_count}
RAPID PILOT opportunities: {rapid_count}
New opportunities this week: {new_ops_count}
Launched this week: {launched_count}
Closed lost this week: {closed_lost_count}"""

    # ULTRA LOGGING - Print the exact context being sent
    print("[BEDROCK ULTRA DEBUG] CONTEXT SENT TO BEDROCK:")
    print(context)
    print("=" * 80)

    # Construct the prompt
    prompt = f"""You are writing a professional intro message for a weekly ACE (AWS Partner Central) hygiene report sent to IT professionals.

{context}

Write a SHORT 2-3 sentence message that:
1. Briefly acknowledges the current stale data status
2. If stale ops decreased or hit zero: Acknowledge the improvement with measured professional tone
3. If consecutive weeks at zero (2+): Recognize the sustained improvement
4. If stale ops increased: State the facts constructively
5. ALWAYS mention Well-Architected count if > 0 (e.g., "including X Well-Architected opportunities")
6. ALWAYS mention RAPID PILOT count if > 0 (e.g., "and X RAPID PILOT opportunities")
7. Mention other key activity metrics (new ops, launched, closed) only if noteworthy
8. TONE: Professional, factual, measured - avoid enthusiastic words like "excellent", "strong", "great"
9. Use words like "good progress", "improvement", "trending positively/negatively"
10. Keep it concise and data-focused

IMPORTANT:
- Do NOT add any greeting like "Hi All" or "Hello team"
- Do NOT add any closing statements or phrases like "pipeline remains healthy and active"
- Return ONLY the 2-3 sentence factual commentary about stale data trends
- Avoid superlatives and overly positive language
- Keep total length under 150 words
- Focus on facts and trends, not cheerleading"""

    try:
        # Initialize Bedrock client with timeout configuration
        from botocore.config import Config
        config = Config(
            connect_timeout=5,
            read_timeout=10,
            retries={'max_attempts': 0}
        )

        bedrock_runtime = boto3.client(
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
