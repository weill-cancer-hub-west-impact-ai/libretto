export type NoteExtractSpecContent = {
  prompt: string;
  schema: string;
  examples: { [key: string]: any }[];
  model_args?: { [key: string]: any };
  note_metadata_query?: string;
  note_text_query?: string;
  example_patient_ids?: string[];
};

export type PromptOnlySpecContent = {
  prompt: string;
  combine_notes?: boolean;
  max_chunk_size?: number;
  example_patient_ids?: string[];
};

export type BlockOrchestratorVariableField = {
  name: string;
  question: string;
  type: 'boolean' | 'categorical' | 'numeric' | 'text';
  allowed_values?: string[];
  format?: string;
};

export type BlockOrchestratorVariable = {
  name: string;
  instruction: string;
};

export type BlockOrchestratorImplementedVariable = {
  name: string;
  fields: BlockOrchestratorVariableField[];
};

export type BlockOrchestratorReviewBlock = {
  id: string;
  name: string;
  condition?: string;
  prompt: string;
  variable_names?: string[];
  note_sequencer?: string;
  incremental: boolean;
  include_previous_reviews: boolean;
  stopping_condition?: string;
  default_values?: any[];
};

export type BlockOrchestratorSynthesisBlock = {
  id: string;
  name: string;
  condition?: string;
  variable_names?: string[];
  prompt: string;
  default_values?: any[];
};

export type BlockOrchestratorImplementation = {
  implementation_policy: string;
  implemented_variables: BlockOrchestratorImplementedVariable[];
  review_blocks?: BlockOrchestratorReviewBlock[];
  synthesis_blocks?: BlockOrchestratorSynthesisBlock[];
};

export type BlockOrchestratorSpecContent = {
  example_patient_ids?: string[];
  variables: BlockOrchestratorVariable[];
  clinical_guidance: string;
  implementation_updated?: boolean;
  implementation?: BlockOrchestratorImplementation;
};

export const DefaultSpecContent = {
  noteextract: {
    prompt: '',
    schema: '',
    examples: []
  },
  prompt_only: {
    prompt: '',
    combine_notes: false,
    max_chunk_size: 100000
  }
};

export type ExtractionSpec = {
  id: string;
  name: string;
  executor: 'noteextract' | 'prompt_only';
  content: any;
  date_added?: string;
  date_modified?: string;
  spec_version?: number;
  is_current?: boolean;
  parent_version_id?: string | null;
};

export type TextRange = {
  start_pos: number;
  end_pos: number;
};

export type Feedback = {
  id?: number;
  annotator_id?: string;
  extraction_id?: number;
  approved: boolean;
  rejected: boolean;
  comment?: string;
  created_at?: string;
  updated_at?: string;
};

export type ExtractionCitation = {
  note_id: string | null;
  quote: string | null;
  char_interval: TextRange | null;
};

export type NoteExtraction = {
  id: number;
  extraction_class: string;
  attributes: { [key: string]: string } | null;
  citations: ExtractionCitation[];
  feedback?: Feedback;
};

export type ExtractionResult = {
  patient_id: string;
  extraction_run: boolean;
  extractions: NoteExtraction[] | null;
};

export type Annotation = {
  note_id?: string | null;
  char_interval: { start_pos: number; end_pos: number } | null;
  source: string;
  sourceName?: string;
  description?: string;
};

export type AnnotationSelection = {
  annotations?: Annotation[];
  source?: string;
};

export type ExtractionAnnotation = Annotation & { extraction: NoteExtraction };

export type Note = {
  id: string;
  metadata: { [key: string]: any };
  note_text: string | null;
  date?: string;
};

export type Patient = {
  id: string;
  notes?: Note[];
  note_count: number;
  earliest_note_date: string | null;
  latest_note_date: string | null;
  metadata: { [key: string]: any };
  tags?: string[];
  extraction_count?: number;
  extraction_run?: boolean;
};

export type Task = {
  id: string;
  model_id: string;
  spec_id: string;
  patient_ids?: string[];
  status: string;
  status_message?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  progress_current?: number;
  progress_total?: number;
  celery_task_id?: string;
  // Fields from JOINed tables
  spec_name?: string;
};

export type Project = {
  id: number;
  name: string;
  source_connection: string;
  created_at?: string;
  updated_at?: string;
};

export type Comment = {
  id: number;
  annotator_id: number;
  username?: string;
  comment: string;
  created_at: string;
  updated_at: string;
  project_id?: number;
};

export type PatientComment = Comment & {
  patient_id: string;
};

export type SpecComment = Comment & {
  spec_id: string;
};

export type GenerationMessage = { role: string; content: string };
