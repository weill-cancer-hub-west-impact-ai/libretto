"""
Unit tests for the LLMExtractDatabase class using SQLAlchemy.
"""

import pytest
import tempfile
import os
import json
from datetime import datetime
from typing import Dict, Any, Tuple

from libretto.database import LLMExtractDatabase
from libretto.types import ExtractionSpec, NoteExtraction


@pytest.fixture
def temp_database():
    """Fixture to create a temporary database for testing."""
    # Create a temporary database file
    test_db_fd, test_db_path = tempfile.mkstemp(suffix='.db')
    os.close(test_db_fd)

    # Create database with SQLite connection string
    connection_string = f"sqlite:///{test_db_path}"
    db = LLMExtractDatabase(connection_string)

    yield db, connection_string, test_db_path

    # Clean up after test
    db.close()
    if os.path.exists(test_db_path):
        os.unlink(test_db_path)


def test_database_initialization(temp_database: Tuple[LLMExtractDatabase, str, str]):
    """Test that database initializes correctly."""
    db, _, _ = temp_database

    # Check that database version is set correctly
    version = db.get_database_version()
    assert version == db.CURRENT_DB_VERSION

    # Check that tables exist by trying to query them
    with db.engine.connect() as conn:
        # Should not raise an exception
        result = conn.execute(db.specs_table.select().limit(0))
        assert result is not None


def test_connection_string_usage(temp_database: Tuple[LLMExtractDatabase, str, str]):
    """Test that the database uses connection_string instead of db_path."""
    db, connection_string, _ = temp_database
    assert db.connection_string == connection_string
    assert db.engine is not None


def test_create_and_get_extraction_task(temp_database: Tuple[LLMExtractDatabase, str, str]):
    """Test creating and retrieving extraction tasks."""
    db, _, _ = temp_database
    task_id = "test_task_123"
    spec_id = "test_spec_456"
    patient_ids = ["patient1", "patient2"]
    project_id = 1

    # Create task
    db.create_extraction_task(task_id, spec_id, patient_ids, project_id)

    # Retrieve task
    task = db.get_task_status(task_id)

    assert task is not None
    assert task['id'] == task_id
    assert task['spec_id'] == spec_id
    assert task['patient_ids'] == patient_ids
    assert task['status'] == 'pending'
    assert task['created_at'] is not None


def test_update_task_status(temp_database: Tuple[LLMExtractDatabase, str, str]):
    """Test updating task status and progress."""
    db, _, _ = temp_database
    task_id = "test_task_update"
    spec_id = "test_spec"
    project_id = 1

    # Create task
    db.create_extraction_task(task_id, spec_id, project_id=project_id)

    # Update to running status
    db.update_task_status(
        task_id,
        'running',
        progress_current=5,
        progress_total=10,
        status_message="Processing patients"
    )

    task = db.get_task_status(task_id)
    assert task['status'] == 'running'
    assert task['progress_current'] == 5
    assert task['progress_total'] == 10
    assert task['status_message'] == "Processing patients"
    assert task['started_at'] is not None

    # Update to completed status
    db.update_task_status(task_id, 'completed')

    task = db.get_task_status(task_id)
    assert task['status'] == 'completed'
    assert task['completed_at'] is not None


def test_cancel_task(temp_database: Tuple[LLMExtractDatabase, str, str]):
    """Test canceling a task."""
    db, _, _ = temp_database
    task_id = "test_task_cancel"
    spec_id = "test_spec"
    project_id = 1

    # Create task
    db.create_extraction_task(task_id, spec_id, project_id=project_id)

    # Cancel task
    result = db.cancel_task(task_id)
    assert result is True

    task = db.get_task_status(task_id)
    assert task['status'] == 'canceled'
    assert task['completed_at'] is not None

    # Try to cancel already completed task - should return False
    result2 = db.cancel_task(task_id)
    assert result2 is False


def test_insert_and_retrieve_extractions(temp_database: Tuple[LLMExtractDatabase, str, str]):
    """Test inserting and retrieving extractions."""
    db, _, _ = temp_database
    patient_id = "patient_123"
    spec_id = "spec_456"

    extractions = [
        {
            'extraction_class': 'medication',
            'citations': [{
                'quote': 'aspirin',
                'note_id': 'note_1',
                'char_interval': {'start_pos': 100, 'end_pos': 107},  
            }],
            'attributes': {'dosage': '81mg'}
        },
        {
            'extraction_class': 'condition',
            'citations': [{
                'quote': 'hypertension',
                'note_id': 'note_1',
                'char_interval': {'start_pos': 200, 'end_pos': 212},
            }],
            'attributes': {'severity': 'mild'}
        }
    ]

    # Insert extractions
    db.insert_extractions(
        patient_id,
        spec_id,
        extractions,
        project_id=1
    )

    # Retrieve extractions
    results = db.get_existing_results(
        {'id': spec_id},
        patient_id,
        project_id=1
    )
    print(results)

    assert results['patient_id'] == patient_id
    assert len(results['extractions']) == 2

    # Check first extraction
    extraction1 = results['extractions'][0]
    assert extraction1['extraction_class'] == 'medication'
    assert len(extraction1['citations']) == 1
    citation1 = extraction1['citations'][0]
    assert citation1['quote'] == 'aspirin'
    assert citation1['char_interval']['start_pos'] == 100
    assert citation1['char_interval']['end_pos'] == 107

    # Check attributes are properly loaded as dict
    assert isinstance(extraction1['attributes'], dict)
    assert extraction1['attributes']['dosage'] == '81mg'


def test_insert_feedback(temp_database: Tuple[LLMExtractDatabase, str, str]):
    """Test inserting and updating feedback."""
    db, _, _ = temp_database
    # First create an extraction to provide feedback on
    patient_id = "patient_feedback"
    spec_id = "spec_feedback"

    db.insert_extractions(
        patient_id,
        spec_id,
        [{
            'extraction_class': 'test',
            'quote': 'test_text',
            'note_id': 'note_1',
            'char_interval': None,
            'attributes': {}
        }],
        project_id=1
    )

    # Get the extraction ID
    results = db.get_existing_results({'id': spec_id}, patient_id, project_id=1)
    extraction_id = results['extractions'][0]['id']

    # Insert feedback
    feedback_data = {
        'extraction_id': extraction_id,
        'annotator_id': 'annotator_1',
        'approved': True,
        'rejected': False,
        'comment': 'Good extraction'
    }

    feedback_id = db.insert_feedback(feedback_data, project_id=1)
    assert feedback_id is not None

    # Update feedback
    feedback_data.update({
        'approved': False,
        'rejected': True,
        'comment': 'Actually, this is incorrect'
    })

    updated_id = db.insert_feedback(feedback_data, project_id=1)
    assert feedback_id + 1 == updated_id  # Should return incremented ID for update


def test_spec_operations(temp_database: Tuple[LLMExtractDatabase, str, str]):
    """Test CRUD operations for specs."""
    db, _, _ = temp_database
    spec_id = "test_spec_crud"

    # Create a spec object (this would normally come from ExtractionSpec)
    spec_data = {
        'id': spec_id,
        'name': 'Test Spec',
        'executor': 'noteextract',
        'content': json.dumps({
            'prompt': 'Test Prompt',
            'schema': 'Test schema',
            'examples': '[]',
            'note_metadata_query': 'SELECT * FROM notes',
            'note_text_query': 'SELECT * FROM notes',
            'model_args': '{}',
        }),
    }

    # Insert spec (this would normally use ExtractionSpec.to_database_value)
    with db.engine.connect() as conn:
        from sqlalchemy import insert
        stmt = insert(db.specs_table).values(
            **spec_data,
            date_added=datetime.now().isoformat(),
            date_modified=datetime.now().isoformat(),
            project_id=1
        )
        conn.execute(stmt)
        conn.commit()

    # Retrieve spec
    retrieved_spec = db.get_spec_by_id(spec_id)
    assert retrieved_spec is not None


def test_overwrite_behavior(temp_database: Tuple[LLMExtractDatabase, str, str]):
    """Test that overwrite behavior works correctly."""
    db, _, _ = temp_database
    patient_id = "patient_overwrite"
    spec_id = "spec_overwrite"

    # Insert initial extractions
    initial_extractions = [{
        'extraction_class': 'medication',
        'citations': [{
            'quote': 'aspirin',
            'note_id': 'note_1',
            'char_interval': {'start_pos': 100, 'end_pos': 107},
        }],
        'attributes': {}
    }]

    db.insert_extractions(
        patient_id, spec_id, initial_extractions, project_id=1
    )

    # Insert new extractions with overwrite=True (default)
    new_extractions = [{
        'extraction_class': 'medication',
        'citations': [{
            'quote': 'ibuprofen',
            'note_id': 'note_1',
            'char_interval': {'start_pos': 200, 'end_pos': 209},
        }],
        'attributes': {}
    }]

    db.insert_extractions(
        patient_id, spec_id, new_extractions, project_id=1
    )

    # Should only have the new extraction
    results = db.get_existing_results({'id': spec_id}, patient_id, project_id=1)
    assert len(results['extractions']) == 1
    assert results['extractions'][0]['citations'][0]['quote'] == 'ibuprofen'


def test_database_version_operations(temp_database: Tuple[LLMExtractDatabase, str, str]):
    """Test database version management."""
    db, _, _ = temp_database
    # Test getting version
    version = db.get_database_version()
    assert isinstance(version, int)

    # Test setting version
    test_version = 99
    db.set_database_version(test_version)
    retrieved_version = db.get_database_version()
    assert retrieved_version == test_version


def test_context_manager(temp_database: Tuple[LLMExtractDatabase, str, str]):
    """Test that database works as context manager."""
    _, _, test_db_path = temp_database
    connection_string = f"sqlite:///{test_db_path}_context"

    with LLMExtractDatabase(connection_string) as db:
        # Should be able to perform operations
        version = db.get_database_version()
        assert isinstance(version, int)

    # Database should be properly closed after context exit
    assert db.engine is not None


def test_get_task_status_nonexistent(temp_database: Tuple[LLMExtractDatabase, str, str]):
    """Test getting status of non-existent task."""
    db, _, _ = temp_database
    result = db.get_task_status("nonexistent_task")
    assert result is None


if __name__ == '__main__':
    # Run the tests
    pytest.main([__file__])