# Single Component Communication with AI Architecture Decision

## Status

Proposed

## Context

Facilitating the communication between the backend and the AI. Other options include allowing components to call the AI directly.

## Decision

Use one component/class to communicate with the AI directly.

## Consequences

### Pros
* Reduces component coupling
* Reduces confusion
* Improves scalability.

### Cons
* Becomes a single point of failure