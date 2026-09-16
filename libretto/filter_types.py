"""
Filter type definitions for patient and extraction filtering.

This module defines TypedDict classes for structured filtering of patients
based on metadata fields and extraction attributes.
"""

from typing import TypedDict, Literal, Any, Optional, List
from .source_database import MetadataFilter

class ExtractionFilter(TypedDict):
    """Filter for extraction classes and attributes.

    Attributes:
        spec_id: ID of the extraction spec to filter on
        extraction_class: Class name of extractions to filter
        attribute: Attribute name within extraction (None for "exists" operator)
        operator: Comparison operator to apply
        value: Value to compare against (None for "exists" operator)
    """
    spec_id: str
    extraction_class: str
    attribute: Optional[str]  # None for "exists" operator
    operator: Literal["eq", "contains", "lt", "gt", "lte", "gte", "exists"]
    value: Optional[Any]  # None for "exists" operator


class FilterRequest(TypedDict, total=False):
    """Request structure for applying filters to patient queries.

    Attributes:
        metadata_filters: List of metadata field filters (all AND'd together)
        extraction_filters: List of extraction filters (all AND'd together)
    """
    metadata_filters: List[MetadataFilter]
    extraction_filters: List[ExtractionFilter]


def validate_metadata_filter(filter_dict: dict) -> MetadataFilter:
    """Validate and normalize a metadata filter dictionary.

    Args:
        filter_dict: Dictionary containing filter specification

    Returns:
        Validated MetadataFilter

    Raises:
        ValueError: If filter structure is invalid
    """
    if not isinstance(filter_dict, dict):
        raise ValueError("Filter must be a dictionary")

    required_fields = ["field", "operator"]
    for field in required_fields:
        if field not in filter_dict:
            raise ValueError(f"Missing required field: {field}")

    operator = filter_dict["operator"]
    if operator not in ["eq", "contains", "lt", "gt", "lte", "gte", "exists"]:
        raise ValueError(f"Invalid operator: {operator}")

    # For "exists" operator, value is ignored but should be present in dict
    if operator == "exists":
        filter_dict["value"] = None
    elif "value" not in filter_dict:
        raise ValueError("Missing required field: value")

    return MetadataFilter(
        field=str(filter_dict["field"]),
        operator=operator,
        value=filter_dict["value"]
    )


def validate_extraction_filter(filter_dict: dict) -> ExtractionFilter:
    """Validate and normalize an extraction filter dictionary.

    Args:
        filter_dict: Dictionary containing filter specification

    Returns:
        Validated ExtractionFilter

    Raises:
        ValueError: If filter structure is invalid
    """
    if not isinstance(filter_dict, dict):
        raise ValueError("Filter must be a dictionary")

    required_fields = ["spec_id", "extraction_class", "operator"]
    for field in required_fields:
        if field not in filter_dict:
            raise ValueError(f"Missing required field: {field}")

    operator = filter_dict["operator"]
    if operator not in ["eq", "contains", "lt", "gt", "lte", "gte", "exists"]:
        raise ValueError(f"Invalid operator: {operator}")

    # For "exists" operator, attribute and value are ignored
    if operator == "exists":
        filter_dict["attribute"] = None
        filter_dict["value"] = None
    else:
        if "attribute" not in filter_dict:
            raise ValueError("Missing required field: attribute")
        if "value" not in filter_dict:
            raise ValueError("Missing required field: value")

    return ExtractionFilter(
        spec_id=str(filter_dict["spec_id"]),
        extraction_class=str(filter_dict["extraction_class"]),
        attribute=filter_dict.get("attribute"),
        operator=operator,
        value=filter_dict.get("value")
    )


def validate_filter_request(request_dict: dict) -> FilterRequest:
    """Validate and normalize a complete filter request.

    Args:
        request_dict: Dictionary containing filter request

    Returns:
        Validated FilterRequest

    Raises:
        ValueError: If request structure is invalid
    """
    result: FilterRequest = {}

    if "metadata_filters" in request_dict:
        if not isinstance(request_dict["metadata_filters"], list):
            raise ValueError("metadata_filters must be a list")
        result["metadata_filters"] = [
            validate_metadata_filter(f) for f in request_dict["metadata_filters"]
        ]

    if "extraction_filters" in request_dict:
        if not isinstance(request_dict["extraction_filters"], list):
            raise ValueError("extraction_filters must be a list")
        result["extraction_filters"] = [
            validate_extraction_filter(f) for f in request_dict["extraction_filters"]
        ]

    return result