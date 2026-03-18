You are part of a documentation-aware AI system.

This project uses a structured **Document System** under the `docs/` directory to manage business and technical documents in a hierarchical and searchable format.

## Folder Structure Overview

```
docs/
├── business/                  # Business documents
│   ├── INDEX.md              # Index file for this folder
│   ├── overview.md           # Project overview
│   └── model.md              # Business model description
│
├── development/              # Development-related documents
│   ├── INDEX.md              # Index file for this folder
│   ├── guideline.md          # Development guide
│   └── coding-rule.md        # Coding standards
│
├── operations/               # (Planned) Operational documents
│   ├── INDEX.md              # Index file for this folder
│   ├── server.md             # Server operations
│   └── monitoring.md         # Monitoring and incident response
```

## Document Characteristics

- All documents are written in Markdown format.
- Each directory contains an `INDEX.md` file listing:
  - The filenames in the same directory
  - A brief description for each

Example:
```markdown
# Development Documents

- `guideline.md`: A guide to the development workflow.
- `coding-rule.md`: Coding standards for this project.
```

## Integration with CLAUDE.md

The AI system does **not directly reference documents**. Instead, it recognizes document availability via `CLAUDE.md`, where paths are listed using the format:

```
@docs/development/INDEX.md
```

This tells the AI:  
- The document exists  
- It may be referenced when needed  
- But the AI should **autonomously decide** which document to consult

## Purpose

The Document System allows AI agents to:
- Navigate structured, maintainable documentation
- Understand the project context through index files
- Autonomously choose and reference relevant documents during tasks
