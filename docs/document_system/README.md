You are part of a documentation-aware AI system.

This project uses a structured **Document System** under the `docs/` directory to manage business and technical documents in a hierarchical and searchable format.

## Folder Structure Overview

```
docs/
├── document_system/          # Meta: rules about the documents themselves
│   ├── README.md             # This file — the SSoT for documentation rules
│   └── templates/            # Format templates, referenced via @ below
│
├── business/                 # Business documents
│   ├── INDEX.md              # Index file for this folder
│   ├── overview.md           # Project overview
│   └── model.md              # Business model description
│
├── development/              # Development-related documents
│   ├── INDEX.md              # Index file for this folder
│   ├── guideline.md          # Development guide
│   └── coding-rule.md        # Coding standards
│
└── operations/               # Operational documents
    ├── INDEX.md              # Index file for this folder
    ├── server.md             # Server operations
    └── monitoring.md         # Monitoring and incident response
```

`docs/document_system/` describes **the documentation system itself**, not the project.
It is meta rather than content, and is therefore **exempt from the `INDEX.md` requirement**.
Every other directory under `docs/` must have one.

## Document Characteristics

- All documents are written in Markdown format.
- Each content directory contains an `INDEX.md` listing the files in that same directory.

## Templates

Every document that accumulates entries over time needs a **format contract**. Without an
explicit upper bound, each change adds "just one more line" — locally correct every time,
compounding globally until the document is unreadable and too expensive to load.

Templates are referenced here so they are always in effect, not merely available:

@docs/document_system/templates/INDEX.template.md
@docs/document_system/templates/roadmap.template.md

A template defines, at minimum:

- the exact shape of one entry,
- what must **not** be written there, and where that content belongs instead,
- a machine-checkable bound.

Projects should enforce these bounds in their own test lane. A rule stated only in prose is
not enforced; prefer a shape that makes the unwanted content impossible to write at all.

## Integration with CLAUDE.md

The AI system does **not directly reference documents**. Instead, it recognizes document
availability via `CLAUDE.md`, where paths are listed using the format:

```
@docs/development/INDEX.md
```

This tells the AI:

- The document exists
- It may be referenced when needed
- But the AI should **autonomously decide** which document to consult

### What may be referenced with `@`

An `@` reference does not merely declare that a document exists — **it inlines the whole
file into every session**. The cost is paid on every turn, whether or not the work touches
that subject. So the list is closed:

- **the `INDEX.md` of each content directory** — what exists, and when to read it,
- **this file** — which carries the format contract and its templates transitively,
- **the development philosophy** — the one document that applies to *every* decision
  rather than to a particular task.

**Everything else is reached through its `INDEX.md` entry.** The entry names the document
and states when to open it; the model decides whether this task is one of those times.

Adding an individual document to `CLAUDE.md` is therefore not a neutral act of "making it
available" — it is a decision to spend context on it unconditionally. A document that only
matters while working on one subject does not qualify, however important it is *within*
that subject.

The same applies to prose written directly in `CLAUDE.md`: if a description also lives in a
document, `CLAUDE.md` is the copy that will go stale.

## Purpose

The Document System allows AI agents to:
- Navigate structured, maintainable documentation
- Understand the project context through index files
- Autonomously choose and reference relevant documents during tasks

Its cost is paid on **every session**, so each document must earn its place. Content that is
cheaper to re-derive from the source of truth — for example where an implementation lives,
which a search answers in seconds — does not belong here.
