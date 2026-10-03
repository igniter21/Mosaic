export type Source =
    | "browser"
    | "youtube"
    | "leetcode"
    | "vscode"
    | "document"
    | "git";

export type PrivacyLevel = "normal" | "sensitive";

export type RetentionClass =
    | "temporary"
    | "short_term"
    | "long_term";

export interface MemoryEvent {
    event_id: string;
    occurred_at: string;
    source: Source;
    event_type: string;
    title: string | null;
    payload: Record<string, unknown>;
    privacy_level: PrivacyLevel;
    retention_class: RetentionClass;
    visit_count: number;
    first_seen_at: string | null;
}

export interface SourceSetting {
    source: Source;
    enabled: boolean;
    updated_at: string;
    model_id: string;
    model_label: string;
    modality: string;
}

export interface DeletionResult {
    deleted_count: number;
    scope: string;
    audit_action: string;
}

export interface GlobalEraseResult {
    raw_events_deleted: number;
    derived_memories_deleted: number;
    embeddings_deleted: number;
    graph_links_deleted: number;
    audit_logs_deleted: number;
    sources_disabled: number;
    vacuum_performed: boolean;
}

export interface MemoryEvidence {
    event: MemoryEvent;
}

export interface MemoryLink {
    memory_id: string;
    relation: string;
    shared_keywords: string[];
}

export interface DerivedMemory {
    id: string;
    occurred_at: string;
    source: Source;
    summary: string;
    keywords: string[];
    model_id: string;
    score: number;
    evidence: MemoryEvidence[];
    links: MemoryLink[];
}

export interface AskMemoryResponse {
    query: string;
    answer: string;
    retrieval_method: string;
    memories: DerivedMemory[];
    generated_at: string;
}
export interface ContextSession {
    id: string;
    started_at: string;
    ended_at: string;
    project_id: string | null;
    summary: string;
    source_count: number;
    event_count: number;
    focus_score: number;
    goal_hint: string | null;
    event_ids: string[];
}

export interface Project {
    id: string;
    name: string;
    slug: string;
    repository: string | null;
    workspace_name: string | null;
    last_seen_at: string;
}

export interface Goal {
    id: string;
    title: string;
    description: string;
    status: string;
    project_id: string | null;
    created_at: string;
    completed_at: string | null;
}

export interface LearningConcept {
    concept: string;
    exposure_count: number;
    practice_count: number;
    implementation_count: number;
    revision_count: number;
    sources: string[];
    first_seen_at: string | null;
    last_seen_at: string | null;
}

export interface LearningGraph {
    concepts: LearningConcept[];
    suggestions: string[];
}

export interface ContextResult {
    query: string;
    answer: string;
    project_id: string | null;
    goal_id: string | null;
    retrieval_method: string;
    memories: DerivedMemory[];
    active_session: ContextSession | null;
    evidence_receipt: Record<string, unknown>;
    generated_at: string;
}

export interface PrivacyLedgerEntry {
    occurred_at: string;
    direction: string;
    provider: string;
    action: string;
    source: string | null;
    bytes_count: number;
    reason: string;
    metadata: Record<string, unknown>;
}

export interface LifecyclePreview {
    expired_memory_ids: string[];
    temporary_candidates: number;
    short_term_candidates: number;
    protected_pinned: number;
}

export interface LifecycleRunResult {
    deleted_memory_count: number;
    deleted_event_count: number;
    dry_run: boolean;
}

export interface SessionDetail extends ContextSession {
    events: MemoryEvent[];
}
