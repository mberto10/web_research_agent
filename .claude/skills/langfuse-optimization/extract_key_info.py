import json
import sys
from pathlib import Path

def extract_trace_info(trace_path):
    """Extract key information from a trace bundle."""
    with open(trace_path, 'r') as f:
        data = json.load(f)
    
    traces = data.get('traces', [])
    observations_by_trace = data.get('observations', {}).get('by_trace', {})
    
    all_trace_info = []
    
    for trace in traces:
        trace_id = trace.get('id')
        observations = observations_by_trace.get(trace_id, [])
        
        info = {
            'trace_id': trace_id,
            'name': trace.get('name'),
            'case_id': trace.get('metadata', {}).get('case_id'),
            'profile': trace.get('metadata', {}).get('profile_name'),
            'tags': trace.get('tags', []),
            'edit_node_issues': [],
            'research_node_issues': [],
            'write_node_issues': [],
            'final_content_preview': None
        }
        
        # Extract node-specific information from observations
        for obs in observations:
            obs_name = obs.get('name', '')
            output = obs.get('output', {})
            
            if 'edit' in obs_name.lower():
                # Extract edit node validation info
                if isinstance(output, dict):
                    validation = output.get('validation_summary', {})
                    if validation:
                        info['edit_node_issues'].append({
                            'pre_flight_score': validation.get('pre_flight_score'),
                            'failed_checks_count': validation.get('failed_checks_count'),
                            'failed_checks': validation.get('failed_checks', [])
                        })
            
            elif 'research' in obs_name.lower():
                # Extract research node info
                if isinstance(output, dict):
                    info['research_node_issues'].append({
                        'tools_used': output.get('tools_used_summary', []),
                        'success_count': output.get('success_count'),
                        'error_count': output.get('error_count')
                    })
            
            elif 'write' in obs_name.lower():
                # Extract write node info
                if isinstance(output, dict):
                    content = output.get('final_content', '')
                    if content:
                        info['final_content_preview'] = str(content)[:500]
        
        all_trace_info.append(info)
    
    return all_trace_info

# Extract from all traces
traces_dir = Path('/tmp/langfuse_analysis')
all_info = []

for trace_file in sorted(traces_dir.glob('trace_*.json')):
    try:
        trace_infos = extract_trace_info(trace_file)
        all_info.extend(trace_infos)
    except Exception as e:
        print(f"Error processing {trace_file}: {e}", file=sys.stderr)

# Output as JSON
print(json.dumps(all_info, indent=2))
