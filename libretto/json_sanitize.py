import numpy as np
from typing import Any
import json

def convert_to_native_types(o: Any) -> Any:
    """
    Removes numpy types and replaces NaN values so that the given object can be
    JSON-serialized.
    """
    if isinstance(o, dict):
        return {convert_to_native_types(k): convert_to_native_types(v) for k, v in o.items()}
    elif isinstance(o, (list, tuple, np.ndarray)):
        return [convert_to_native_types(v) for v in o]
    elif isinstance(o, (float, int)) and np.isnan(o):
        return None
    elif isinstance(o, float):
        return round(o, 6)
    elif isinstance(o, np.generic):
        v = o.item()
        if isinstance(v, float): return round(v, 6)
        return v
    return o

def safe_load_json(o: str) -> Any:
    """Load a JSON string without throwing exceptions."""
    try:
        return json.loads(o)
    except json.JSONDecodeError as e:
        return None