#!/usr/bin/env python3
"""
Test script for AWS Bedrock integration
"""

from bedrock_client import generate_intro_message

# Test Case 1: Stale ops improving
print("=" * 80)
print("TEST 1: Stale ops improving (from 5 to 2)")
print("=" * 80)

current_stats = {
    'stale_ops_count': 2,
    'consecutive_weeks_no_stale': 0,
    'total_reportable_ops': 58,
    'total_open_ops': 58
}

previous_stats = {
    'stale_ops_count': 5,
    'consecutive_weeks_no_stale': 0
}

comparison_data = {
    'new_ops': [1, 2, 3],  # 3 new ops
    'status_changes': [
        {'new_stage': 'Launched', 'opportunity_id': 'O123'},
        {'new_stage': 'Launched', 'opportunity_id': 'O456'},
        {'new_stage': 'Closed Lost', 'opportunity_id': 'O789'}
    ]
}

intro = generate_intro_message(current_stats, previous_stats, comparison_data)
print(f"\nGenerated Intro:\n{intro}\n")

# Test Case 2: Hit zero stale ops (first time)
print("=" * 80)
print("TEST 2: Hit zero stale ops for first time")
print("=" * 80)

current_stats = {
    'stale_ops_count': 0,
    'consecutive_weeks_no_stale': 1,
    'total_reportable_ops': 60,
    'total_open_ops': 60
}

previous_stats = {
    'stale_ops_count': 3,
    'consecutive_weeks_no_stale': 0
}

comparison_data = {
    'new_ops': [1, 2],
    'status_changes': [
        {'new_stage': 'Launched', 'opportunity_id': 'O123'}
    ]
}

intro = generate_intro_message(current_stats, previous_stats, comparison_data)
print(f"\nGenerated Intro:\n{intro}\n")

# Test Case 3: Multiple weeks at zero
print("=" * 80)
print("TEST 3: 3 consecutive weeks with zero stale ops")
print("=" * 80)

current_stats = {
    'stale_ops_count': 0,
    'consecutive_weeks_no_stale': 3,
    'total_reportable_ops': 62,
    'total_open_ops': 62
}

previous_stats = {
    'stale_ops_count': 0,
    'consecutive_weeks_no_stale': 2
}

comparison_data = {
    'new_ops': [1],
    'status_changes': []
}

intro = generate_intro_message(current_stats, previous_stats, comparison_data)
print(f"\nGenerated Intro:\n{intro}\n")

# Test Case 4: Stale ops increased
print("=" * 80)
print("TEST 4: Stale ops increased (from 2 to 6)")
print("=" * 80)

current_stats = {
    'stale_ops_count': 6,
    'consecutive_weeks_no_stale': 0,
    'total_reportable_ops': 55,
    'total_open_ops': 55
}

previous_stats = {
    'stale_ops_count': 2,
    'consecutive_weeks_no_stale': 0
}

comparison_data = {
    'new_ops': [],
    'status_changes': [
        {'new_stage': 'Closed Lost', 'opportunity_id': 'O789'},
        {'new_stage': 'Closed Lost', 'opportunity_id': 'O790'}
    ]
}

intro = generate_intro_message(current_stats, previous_stats, comparison_data)
print(f"\nGenerated Intro:\n{intro}\n")

print("=" * 80)
print("Testing complete!")
print("=" * 80)
