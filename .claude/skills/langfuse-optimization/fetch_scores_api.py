#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Add helpers directory to path
sys.path.insert(0, str(Path(__file__).parent / 'helpers'))
from langfuse_client import get_langfuse_client

def serialize_score(score):
    """Convert score object to JSON-serializable dict."""
    if hasattr(score, 'dict'):
        score_dict = score.dict()
    else:
        score_dict = score
    
    # Convert datetime objects to strings
    result = {}
    for key, value in score_dict.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result

client = get_langfuse_client()

# Trace IDs from annotation queue
trace_ids = [
    "2fd22e149d0e2846d35799a220b67d76",
    "cd5fd9690dc0943e8a9ac2cf8dbcc1dd",
    "aed4face8439d08afc35df52ab8d9f96",
    "4d9359d511bd05f3e5cc6e8f675db430",
    "106b5531a31ada3d87eab5b09c25452e"
]

traces_with_scores = []

for trace_id in trace_ids:
    try:
        # Fetch trace with scores
        trace = client.api.trace.get(trace_id)
        
        if not trace:
            print(f"✗ Trace not found: {trace_id}", file=sys.stderr)
            continue
        
        trace_dict = trace.dict() if hasattr(trace, 'dict') else trace
        
        trace_info = {
            'id': trace_dict.get('id'),
            'name': trace_dict.get('name'),
            'case_id': trace_dict.get('metadata', {}).get('case_id'),
            'profile': trace_dict.get('metadata', {}).get('profile_name'),
            'scores': [serialize_score(s) for s in trace_dict.get('scores', [])]
        }
        
        traces_with_scores.append(trace_info)
        print(f"✓ {trace_info['name'][:60]}... ({len(trace_info['scores'])} scores)", file=sys.stderr)
        
    except Exception as e:
        print(f"✗ Error fetching trace {trace_id}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)

print(json.dumps(traces_with_scores, indent=2))
