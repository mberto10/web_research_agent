import os
import sys
import json
from langfuse import Langfuse

# Initialize Langfuse client
client = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
)

# Trace IDs from annotation queue
trace_ids = [
    "2fd22e149d0e2846d35799a220b67d76",
    "cd5fd9690dc0943e8a9ac2cf8dbcc1dd",
    "aed4face8439d08afc35df52ab8d9f96",
    "4d9359d511bd05f3e5cc6e8f675db430",
    "106b5531a31ada3d87eab5b09c25452e"
]

traces_with_scores = []

# Fetch traces using the client's fetch API
for trace_id in trace_ids:
    try:
        # Use client.fetch_trace instead
        trace = client.fetch_trace(trace_id)
        trace_info = {
            'id': trace.id,
            'name': trace.name,
            'metadata': trace.metadata,
            'scores': []
        }
        
        # Get scores
        if hasattr(trace, 'scores') and trace.scores:
            for score in trace.scores:
                score_dict = {
                    'name': score.name,
                    'value': score.value,
                }
                if hasattr(score, 'comment'):
                    score_dict['comment'] = score.comment
                trace_info['scores'].append(score_dict)
        
        traces_with_scores.append(trace_info)
        print(f"✓ Fetched trace: {trace.name[:60]}... ({len(trace_info['scores'])} scores)", file=sys.stderr)
        
    except Exception as e:
        print(f"✗ Error fetching trace {trace_id}: {e}", file=sys.stderr)

print(json.dumps(traces_with_scores, indent=2))
