export type Source =
    | "browser"
    | "youtube"
    | "leetcode"
    | "vscode"
    | "document";

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
