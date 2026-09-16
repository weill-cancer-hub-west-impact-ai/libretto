/**
 * Utility for managing patient view and note view state in local storage
 * Shared between PatientSelector, PatientView, and other components
 */

// Storage keys
const ACTIVE_TAG_KEY = 'activeTagFilter';
const PATIENT_VIEW_TYPE_KEY = 'patientViewType';
const PATIENT_SEARCH_TARGET_KEY = 'patientSearchTarget';
const PATIENT_SORT_KEY = 'patientSort';
const PATIENT_SORT_FIELD_KEY = 'patientSortField';
const PATIENT_METADATA_FIELD_KEY = 'patientMetadataField';
const PATIENT_METADATA_FILTERS_KEY = 'patientMetadataFilters';
const PATIENT_EXTRACTION_FILTERS_KEY = 'patientExtractionFilters';
const NOTE_VIEW_TYPE_KEY = 'noteViewType';
const NOTE_SORT_KEY = 'noteSort';
const NOTE_SORT_FIELD_KEY = 'noteSortField';
const NOTE_METADATA_FIELD_KEY = 'noteMetadataField';

// Valid values for validation
const VALID_PATIENT_VIEW_TYPES = [
  'note_count',
  'extraction_count',
  'earliest_date',
  'latest_date',
  'metadata_field'
];

const VALID_SEARCH_TARGETS = ['all', 'id', 'text', 'metadata'];

const VALID_NOTE_VIEW_TYPES = ['note_date', 'metadata_field'];

const VALID_SORT_OPTIONS = ['asc', 'desc'];

const VALID_SORT_FIELD_OPTIONS = ['name', 'value', null];

// Interface for patient view state
export interface PatientViewState {
  activeTag: string | null;
  viewType: string;
  searchTarget: string;
  sort: string;
  sortField: string | null;
  metadataFieldName: string;
  metadataFilters: string;
  extractionFilters: string;
}

// Interface for note view state
export interface NoteViewState {
  viewType: string;
  sort: string;
  sortField: string | null;
  metadataFieldName: string;
}

// Default values
const DEFAULT_PATIENT_VIEW_STATE: PatientViewState = {
  activeTag: null,
  viewType: 'note_count',
  searchTarget: 'all',
  sort: 'desc',
  sortField: null,
  metadataFieldName: '',
  metadataFilters: '[]',
  extractionFilters: '[]'
};

const DEFAULT_NOTE_VIEW_STATE: NoteViewState = {
  viewType: 'note_date',
  sort: 'desc',
  sortField: null,
  metadataFieldName: ''
};

/**
 * Utility function to safely get and validate values from localStorage
 */
function getValidatedValue<T extends string | null>(
  key: string,
  validValues: (string | null)[],
  defaultValue: T
): T {
  try {
    const stored = localStorage.getItem(key);
    if (stored && (validValues.length === 0 || (validValues as string[]).includes(stored))) {
      return stored as T;
    }
  } catch (error) {
    console.warn(`Failed to load ${key} from local storage:`, error);
  }
  return defaultValue;
}

/**
 * Utility function to safely set values in localStorage
 */
function setValue(key: string, value: string | null): void {
  try {
    if (value === null) {
      localStorage.removeItem(key);
    } else {
      localStorage.setItem(key, value);
    }
  } catch (error) {
    console.warn(`Failed to save ${key} to local storage:`, error);
  }
}

// Legacy functions for backwards compatibility
export function saveActiveTag(tag: string | null): void {
  setValue(ACTIVE_TAG_KEY, tag);
}

export function loadActiveTag(): string | null {
  try {
    return localStorage.getItem(ACTIVE_TAG_KEY);
  } catch (error) {
    console.warn('Failed to load active tag from local storage:', error);
    return null;
  }
}

// Patient view state functions
export function savePatientViewState(state: Partial<PatientViewState>): void {
  if (state.activeTag !== undefined) {
    setValue(ACTIVE_TAG_KEY, state.activeTag);
  }
  if (state.viewType !== undefined) {
    setValue(PATIENT_VIEW_TYPE_KEY, state.viewType);
  }
  if (state.searchTarget !== undefined) {
    setValue(PATIENT_SEARCH_TARGET_KEY, state.searchTarget);
  }
  if (state.sort !== undefined) {
    setValue(PATIENT_SORT_KEY, state.sort);
  }
  if (state.sortField !== undefined) {
    setValue(PATIENT_SORT_FIELD_KEY, state.sortField);
  }
  if (state.metadataFieldName !== undefined) {
    setValue(PATIENT_METADATA_FIELD_KEY, state.metadataFieldName);
  }
  if (state.metadataFilters !== undefined) {
    setValue(PATIENT_METADATA_FILTERS_KEY, state.metadataFilters);
  }
  if (state.extractionFilters !== undefined) {
    setValue(PATIENT_EXTRACTION_FILTERS_KEY, state.extractionFilters);
  }
}

export function loadPatientViewState(): PatientViewState {
  return {
    activeTag: loadActiveTag(),
    viewType: getValidatedValue(
      PATIENT_VIEW_TYPE_KEY,
      VALID_PATIENT_VIEW_TYPES,
      DEFAULT_PATIENT_VIEW_STATE.viewType
    ),
    searchTarget: getValidatedValue(
      PATIENT_SEARCH_TARGET_KEY,
      VALID_SEARCH_TARGETS,
      DEFAULT_PATIENT_VIEW_STATE.searchTarget
    ),
    sort: getValidatedValue(PATIENT_SORT_KEY, VALID_SORT_OPTIONS, DEFAULT_PATIENT_VIEW_STATE.sort),
    sortField: getValidatedValue(
      PATIENT_SORT_FIELD_KEY,
      VALID_SORT_FIELD_OPTIONS,
      DEFAULT_PATIENT_VIEW_STATE.sortField
    ),
    metadataFieldName: getValidatedValue(
      PATIENT_METADATA_FIELD_KEY,
      [], // No validation needed for metadata field names
      DEFAULT_PATIENT_VIEW_STATE.metadataFieldName
    ),
    metadataFilters: getValidatedValue(
      PATIENT_METADATA_FILTERS_KEY,
      [], // No validation needed for JSON strings
      DEFAULT_PATIENT_VIEW_STATE.metadataFilters
    ),
    extractionFilters: getValidatedValue(
      PATIENT_EXTRACTION_FILTERS_KEY,
      [], // No validation needed for JSON strings
      DEFAULT_PATIENT_VIEW_STATE.extractionFilters
    )
  };
}

// Note view state functions
export function saveNoteViewState(state: Partial<NoteViewState>): void {
  if (state.viewType !== undefined) {
    setValue(NOTE_VIEW_TYPE_KEY, state.viewType);
  }
  if (state.sort !== undefined) {
    setValue(NOTE_SORT_KEY, state.sort);
  }
  if (state.sortField !== undefined) {
    setValue(NOTE_SORT_FIELD_KEY, state.sortField);
  }
  if (state.metadataFieldName !== undefined) {
    setValue(NOTE_METADATA_FIELD_KEY, state.metadataFieldName);
  }
}

export function loadNoteViewState(): NoteViewState {
  return {
    viewType: getValidatedValue(
      NOTE_VIEW_TYPE_KEY,
      VALID_NOTE_VIEW_TYPES,
      DEFAULT_NOTE_VIEW_STATE.viewType
    ),
    sort: getValidatedValue(NOTE_SORT_KEY, VALID_SORT_OPTIONS, DEFAULT_NOTE_VIEW_STATE.sort),
    sortField: getValidatedValue(
      NOTE_SORT_FIELD_KEY,
      VALID_SORT_FIELD_OPTIONS,
      DEFAULT_NOTE_VIEW_STATE.sortField
    ),
    metadataFieldName: getValidatedValue(
      NOTE_METADATA_FIELD_KEY,
      [], // No validation needed for metadata field names
      DEFAULT_NOTE_VIEW_STATE.metadataFieldName
    )
  };
}


// Reset functions
export function resetPatientViewState(): void {
  try {
    localStorage.removeItem(ACTIVE_TAG_KEY);
    localStorage.removeItem(PATIENT_VIEW_TYPE_KEY);
    localStorage.removeItem(PATIENT_SEARCH_TARGET_KEY);
    localStorage.removeItem(PATIENT_SORT_KEY);
    localStorage.removeItem(PATIENT_SORT_FIELD_KEY);
    localStorage.removeItem(PATIENT_METADATA_FIELD_KEY);
    localStorage.removeItem(PATIENT_METADATA_FILTERS_KEY);
    localStorage.removeItem(PATIENT_EXTRACTION_FILTERS_KEY);
  } catch (error) {
    console.warn('Failed to reset patient view state:', error);
  }
}

export function resetNoteViewState(): void {
  try {
    localStorage.removeItem(NOTE_VIEW_TYPE_KEY);
    localStorage.removeItem(NOTE_SORT_KEY);
    localStorage.removeItem(NOTE_SORT_FIELD_KEY);
    localStorage.removeItem(NOTE_METADATA_FIELD_KEY);
  } catch (error) {
    console.warn('Failed to reset note view state:', error);
  }
}

export function resetAllBrowseState(): void {
  resetPatientViewState();
  resetNoteViewState();
}
