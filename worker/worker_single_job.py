import logging
import os
import signal
import threading
import traceback
import numpy as np
import uuid
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from libretto.database import LLMExtractDatabase
from libretto.source_database import SourceDatabase, DEFAULT_NOTE_METADATA_QUERY, DEFAULT_NOTE_TEXT_QUERY
from libretto.types import project_environment

from .worker import (
    run_noteextract_and_store,
    run_prompt_only_and_store,
)

logger = logging.getLogger(__name__)

LLM_SLEEP_INTERVAL = 1

def _extract_for_patient(
    db: LLMExtractDatabase,
    task_id: str,
    spec: dict,
    project: dict,
    patient_id: str,
    spec_id: str,
    project_id: Optional[int],
    source_db_connection: str,
    cancel_event: threading.Event,
) -> int:
    if cancel_event.is_set():
        return 0

    if db.get_existing_results(spec, patient_id, project_id=project_id).get("extractions"):
        return 0

    note_metadata_query = project.get("note_metadata_query") or os.getenv("NOTE_METADATA_QUERY", DEFAULT_NOTE_METADATA_QUERY)
    note_text_query = project.get("note_text_query") or os.getenv("NOTE_TEXT_QUERY", DEFAULT_NOTE_TEXT_QUERY)
    query_spec = {
        "note_metadata_query": note_metadata_query,
        "note_text_query": note_text_query,
    }

    source_db = SourceDatabase(source_db_connection)
    patient_data = source_db.get_notes(query_spec, patient_ids=[patient_id])

    if not patient_data:
        logger.info(f"No notes found for patient {patient_id}")
        return 0

    def is_canceled():
        if cancel_event.is_set(): return True
        current_task = db.get_task_status(task_id)
        if current_task and current_task.get('status') == 'canceled':
            logger.info(f"Task {task_id} was canceled")
            return True
        return False

    executor = spec['executor']
    config = spec.get('content') or {}

    if executor == 'noteextract':
        run_fn = run_noteextract_and_store
    elif executor == 'prompt_only':
        run_fn = run_prompt_only_and_store
    else:
        raise ValueError(f"Unsupported executor '{executor}'")

    num_extracted = run_fn(
        db=db,
        patient_data=patient_data,
        spec_id=spec_id,
        project_id=project_id,
        config=config,
        cancel_check=is_canceled,
    )

    time.sleep(LLM_SLEEP_INTERVAL)

    return num_extracted


def run_single_job(
    db_conn: str,
    project_id: int,
    spec_id: str,
    patient_ids: Optional[List[str]],
    patient_tag: Optional[str],
    patient_sample_size: Optional[int],
    overwrite: bool,
    workers: int = 1,
) -> None:
    db = LLMExtractDatabase(db_conn, enable_wal=True)
    task_id = str(uuid.uuid4())
    cancel_event = threading.Event()

    def _handle_signal(signum, frame):
        logger.info(f"Received signal {signum}, canceling task {task_id}...")
        cancel_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        project = db.get_project_by_id(project_id)
        if not project:
            raise ValueError(f"Project with ID {project_id} not found")

        source_db_connection = project.get("source_connection")
        if not source_db_connection:
            raise ValueError(f"Project {project_id} does not specify a source database connection")

        spec = db.get_spec_by_id(spec_id)
        if not spec:
            raise ValueError(f"Spec with ID {spec_id} not found")

        with project_environment(project):
            note_metadata_query = project.get("note_metadata_query") or os.getenv("NOTE_METADATA_QUERY", DEFAULT_NOTE_METADATA_QUERY)
            note_text_query = project.get("note_text_query") or os.getenv("NOTE_TEXT_QUERY", DEFAULT_NOTE_TEXT_QUERY)
            query_spec = {
                "note_metadata_query": note_metadata_query,
                "note_text_query": note_text_query,
            }

            if patient_ids is not None:
                resolved_patients = patient_ids
            elif patient_tag is not None:
                resolved_patients = db.get_patients_with_tag(patient_tag, project_id)
                if not resolved_patients:
                    raise ValueError(f"No patients found with tag '{patient_tag}' in project {project_id}")
            else:
                logger.info("Resolving full patient list from source database...")
                source_db = SourceDatabase(source_db_connection)
                all_patient_data = source_db.get_notes(query_spec, patient_ids=None)
                if not all_patient_data:
                    raise ValueError("No patients found in source database")
                resolved_patients = [p["id"] for p in all_patient_data]

            if patient_sample_size is not None and patient_sample_size < len(resolved_patients):
                np.random.seed(0)  # ensure reproducibility for caching
                resolved_patients = [resolved_patients[i] for i in np.random.choice(len(resolved_patients), size=patient_sample_size, replace=False)]
                logger.info("Extracting from sample of %d patients...", len(resolved_patients))

            if overwrite:
                db.clear_existing_results(extraction_source=spec, patient_ids=resolved_patients, project_id=project_id)

            db.create_extraction_task(task_id, spec_id, resolved_patients, project_id)
            logger.info(f"Created task {task_id} for {len(resolved_patients)} patients")

            db.update_task_status(task_id, "running", progress_total=len(resolved_patients))

            progress_lock = threading.Lock()
            progress_current = 0
            errors = []

            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_patient = {
                    executor.submit(
                        _extract_for_patient,
                        db, task_id, spec, project,
                        pid, spec_id, project_id,
                        source_db_connection, cancel_event,
                    ): pid
                    for pid in resolved_patients
                }

                try:
                    for future in as_completed(future_to_patient):
                        pid = future_to_patient[future]
                        while True:
                            try:
                                if cancel_event.is_set() or (db.get_task_status(task_id) or {}).get('status') == 'canceled':
                                    logger.info(f"Task {task_id} was canceled")
                                    executor.shutdown(wait=False, cancel_futures=True)
                                    break
                                future.result(timeout=1)
                            except Exception as e:
                                logger.error(f"Patient {pid} failed: {e}\n{traceback.format_exc()}")
                                errors.append((pid, str(e)))
                            finally:
                                break

                        with progress_lock:
                            progress_current += 1
                            current = progress_current

                        if cancel_event.is_set() or (db.get_task_status(task_id) or {}).get('status') == 'canceled':
                            logger.info(f"Task {task_id} was canceled")
                            executor.shutdown(wait=False, cancel_futures=True)
                            break
                        db.update_task_status(task_id, "running", progress_current=current)

                except KeyboardInterrupt:
                    logger.info("Cancellation requested, shutting down executor...")
                    executor.shutdown(wait=False, cancel_futures=True)

        if cancel_event.is_set():
            db.update_task_status(task_id, "canceled", status_message="Task canceled by signal")
            logger.info(f"Task {task_id} canceled")
        elif errors:
            error_summary = "; ".join(f"{pid}: {msg}" for pid, msg in errors[:5])
            db.update_task_status(
                task_id, "failed",
                error_message=f"{len(errors)} patient(s) failed. First errors: {error_summary}",
                progress_current=progress_current,
            )
            logger.info(f"Task {task_id} completed with {len(errors)} error(s)")
        else:
            db.update_task_status(
                task_id, "completed",
                status_message=f"Processed {progress_current}/{len(resolved_patients)} patients successfully",
                progress_current=progress_current,
            )
            logger.info(f"Task {task_id} completed successfully")

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}\n{traceback.format_exc()}")
        try:
            db.update_task_status(task_id, "failed", error_message=f"Task failed: {e}\n{traceback.format_exc()}")
        except Exception:
            pass
        raise
    finally:
        db.close()
