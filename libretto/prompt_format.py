import numpy as np
import json
from collections import Counter
from .types import Patient, Note

def create_metadata_summary(all_metadata: list[dict]):
    # Parse metadata and collect all unique keys and their values
    metadata_summary = {}
    
    # Analyze each unique metadata key
    if not all_metadata: return metadata_summary

    all_keys = set()
    for meta in all_metadata:
        all_keys.update(meta.keys())
    
    for key in all_keys:
        values = []
        object_type = False
        for meta in all_metadata:
            v = meta.get(key)
            if v is not None:
                if isinstance(v, (dict, list)):
                    object_type = True
                    v = json.dumps(v)
                values.append(v)

        print(key, values)
        if not values:
            continue
            
        # Determine if values are numeric or categorical
        if object_type:
            np.random.seed(0) # ensure reproducibility for caching
            metadata_summary[key] = {
                'type': 'object',
                'samples': [values[i] for i in np.random.choice(len(values), replace=False, size=min(len(values), 10))],
                'total_records': len(values)
            }
        else:
            try:
                numeric_values = [float(v) for v in values if str(v).replace('.', '').replace('-', '').isdigit()]
                if len(numeric_values) > len(values) * 0.5:  # Mostly numeric
                    metadata_summary[key] = {
                        'type': 'numeric',
                        'mean': np.mean(numeric_values),
                        'count': len(numeric_values),
                        'total_records': len(values)
                    }
                else:
                    # Categorical - show most common values
                    value_counts = Counter(values)
                    metadata_summary[key] = {
                        'type': 'categorical',
                        'most_common': value_counts.most_common(20),
                        'unique_count': len(value_counts),
                        'total_records': len(values)
                    }
            except (ValueError, TypeError):
                # Treat as categorical if numeric conversion fails
                value_counts = Counter(values)
                metadata_summary[key] = {
                    'type': 'categorical',
                    'most_common': value_counts.most_common(20),
                    'unique_count': len(value_counts),
                    'total_records': len(values)
                }
    return metadata_summary

def create_dataset_summary(patients: list[Patient]) -> str:
    if not patients: return ""

    lines = [
        "PATIENTS",
        "-----",
        f"• {len(patients)} total patients",
        f"• {sum(len(p.get('notes', [])) for p in patients) / len(patients):.2f} notes per patient",
        f"• Min notes per patient: {min(len(p.get('notes', [])) for p in patients)}",
        f"• Max notes per patient: {max(len(p.get('notes', [])) for p in patients)}",
    ]
    return "\n".join(lines)

def format_note_preview(metadata: list[Patient] | None = None, sample_notes: list[Patient] | None = None, max_note_length=1000, first_n=3, max_notes_per_patient=20):
    """
    Formats patient notes into a string suitable for passing to an LLM.
    
    Args:
        metadata: Patient list containing metadata for all patients
        sample_notes: Patient list containing notes for a sample of patients
        max_note_length: Maximum length for abbreviated note text (truncated in middle)
    
    Returns:
        Formatted string with metadata summary and sample notes
    """
    if metadata:
        dataset_summary = create_dataset_summary(metadata)
        patient_meta_summary = create_metadata_summary([p["metadata"] for p in metadata])
        note_meta_summary = create_metadata_summary([n["metadata"] for p in metadata for n in p.get("notes")])
    else:
        dataset_summary = ""
        patient_meta_summary = ""
        note_meta_summary = ""
    
    # Function to truncate text in the middle
    def truncate_middle(text, max_length):
        if len(text) <= max_length:
            return text
        
        # Remove extra whitespace and newlines for cleaner display
        text = ' '.join(text.split())
        
        if len(text) <= max_length:
            return text
            
        half_length = (max_length - 5) // 2  # Account for " ... "
        return text[:half_length] + " ... " + text[-half_length:]
    
    # Build the formatted string
    output = []

    if dataset_summary:
        output.append(dataset_summary)

    # Metadata summaries
    if patient_meta_summary:
        output.append("PATIENT METADATA FIELDS:")
        output.append("-----")
        
        for key, info in patient_meta_summary.items():
            if info['type'] == 'numeric':
                output.append(f"• `{key}`: Numeric (mean: {info['mean']:.2f}, {info['count']}/{info['total_records']} records)")
            elif info['type'] == 'object':
                output.append(f"• `{key}`: Object")
                output.append(f"  Samples: " + ', '.join(str(v) for v in info['samples']))
            else:
                most_common_str = ", ".join([f"'{v}' ({c})" for v, c in info['most_common'][:10]])
                output.append(f"• `{key}`: Categorical ({info['unique_count']} unique values)")
                output.append(f"  Most common: {most_common_str}")
        output.append("")

    if note_meta_summary:
        output.append("NOTE METADATA FIELDS:")
        output.append("-----")
        
        for key, info in note_meta_summary.items():
            if info['type'] == 'numeric':
                output.append(f"• `{key}`: Numeric (mean: {info['mean']:.2f}, {info['count']}/{info['total_records']} records)")
            elif info['type'] == 'object':
                output.append(f"• `{key}`: Object")
                output.append(f"  Samples: " + ', '.join(str(v) for v in info['samples']))
            else:
                most_common_str = ", ".join([f"'{v}' ({c})" for v, c in info['most_common'][:10]])
                output.append(f"• `{key}`: Categorical ({info['unique_count']} unique values)")
                output.append(f"  Most common: {most_common_str}")
        output.append("")

    # Sample notes
    if sample_notes:
        output.append("SAMPLE PATIENTS:")
        output.append("-----")

        for i, patient in enumerate(sample_notes[:first_n]):
            output.append(f"Sample Patient #{i+1}:")
            output.append(json.dumps({
                **patient,
                "notes": [{
                    **note,
                    "note_text": truncate_middle(note.get("note_text", ""), max_note_length)
                } for note in patient.get("notes", [])[:max_notes_per_patient]]
            }, indent=2))
        
    return "\n".join(output)

