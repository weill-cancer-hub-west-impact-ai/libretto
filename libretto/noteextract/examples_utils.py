import json
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import langextract as lx
import pandas as pd

def chunk_keys(df: pd.DataFrame) -> List[object]:
    ordered = []
    seen = set()
    for chunk_text in df["chunk_text"]:
        key = chunk_text
        if key not in seen:
            seen.add(key)
            ordered.append(key)
    return ordered

def resolve_chunk_text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    path = Path(text)
    if path.suffix.lower() == ".txt" and path.exists():
        return path.read_text(encoding="utf-8").strip()
    return text

def build_examples(example_df: pd.DataFrame, num_examples: int | None = None) -> List[lx.data.ExampleData]:
    if num_examples is not None:
        example_df = example_df.head(num_examples)
    keys = chunk_keys(example_df)
    grouped = example_df.groupby("chunk_text", sort=False)
    attribute_columns = [
        col
        for col in example_df.columns
        if col not in {"extraction_text", "extraction_class", "chunk_text"}
    ]
    examples: List[lx.data.ExampleData] = []
    for key in keys:
        chunk_rows = grouped.get_group(key)
        chunk_text = resolve_chunk_text(chunk_rows["chunk_text"].iloc[0])
        if not chunk_text:
            continue
        extractions = []
        
        for _, row in chunk_rows.iterrows():
            extraction_text = row.get("extraction_text")
            extraction_class = row.get("extraction_class")
            if pd.isna(extraction_text) or str(extraction_text).strip() == "":
                continue
            if pd.isna(extraction_class) or str(extraction_class).strip() == "":
                continue
            attrs = {
                col: row[col]
                for col in attribute_columns
                if pd.notna(row[col]) and str(row[col]).strip()
            }
            attrs = {k: str(v).strip() for k, v in attrs.items()}
            extraction = lx.data.Extraction(
                extraction_class=str(extraction_class).strip(),
                extraction_text=str(extraction_text).strip(),
                attributes=attrs,
            )
            extractions.append(extraction)
        if extractions:
            examples.append(lx.data.ExampleData(text=chunk_text, extractions=extractions))
    return examples

def standardize_examples(examples: list[lx.data.ExampleData]) -> list[dict]:
    standardized = []
    for example in examples:
        standardized.append(
            {
                "text": example.text,
                "extractions": [
                    {
                        "extraction_class": extraction.extraction_class,
                        "extraction_text": extraction.extraction_text,
                        "attributes": extraction.attributes or {},
                    }
                    for extraction in example.extractions
                ],
            }
        )
    return standardized

def add_ex_to_config(config_path: str, example_df: pd.DataFrame, num_examples: int | None = None):
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    examples = build_examples(example_df, num_examples)
    config["lx_examples"] = standardize_examples(examples)
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=4)
