# Local retrieval and derived memories

## What Mosaic derives

Each approved raw event is first routed by its declared source to one local
metadata model. Browser events use the web activity model, YouTube uses the
video activity model, LeetCode uses the coding-practice model, VS Code uses the
code-workspace model, and documents use the document-metadata model. These
models receive only the source-specific metadata named on the **Data Sources**
page; they do not receive page bodies, video/audio, editor content, or document
text.

Every local model produces the same canonical understanding, so one shared
memory pipeline produces a derived memory containing:

- a deterministic, source-aware summary such as “Watched Python sorting tutorial”;
- searchable keywords extracted from the event’s existing local metadata;
- a 192-dimension local feature-hash vector; and
- graph links to other derived memories that share meaningful keywords.

The vector is not a hosted embedding and requires neither an API key nor network access. It is a deterministic feature-hash representation used alongside keyword overlap to rank local activity. Its stored model ID records which local model profile processed the original source.

## Asking a question

`POST /api/v1/memory/ask` accepts a `query` and optional `limit`. It supports ordinary topic queries plus local time phrases including **today**, **yesterday**, **last week**, and **last seven days**. It returns a concise deterministic answer, ranked derived memories, source metadata, relation links, and the raw events that support every result.

For example:

```json
{
  "query": "What was I learning about Python?",
  "limit": 5
}
```

The response explicitly names its retrieval method: `local lexical ranking + feature-hash similarity`. It should be read as a ranked account of stored evidence, not a claim that goes beyond it.

## Retention and deletion

Derived memories, embeddings, evidence rows, and graph links are local derived data. Deleting a raw event deletes its related derived memory. The **Erase all local memory** action deletes all raw and derived records before SQLite compaction. Disabling a source prevents new raw or derived data from that source.
