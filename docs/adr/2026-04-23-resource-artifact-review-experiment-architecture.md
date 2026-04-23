# ADR: Resource, Artifact, Review, and Experiment Architecture

- Status: Accepted
- Date: 2026-04-23

## Context

TextFlow is expanding from a linear preprocessing utility into a project-oriented desktop platform that needs richer corpus selection, artifact inspection, human review, and experiment comparison without breaking offline packaging or reproducibility. The current workflow runtime already models deterministic processing as a directed graph, but product-facing concerns such as reusable resource selections and review queues should remain inspectable project records instead of becoming hidden node state.

## Decision

We will keep deterministic transforms inside DAG nodes and promote resource, review, and experiment concepts to explicit project-level records.

The architecture decisions are:

1. Deterministic transforms stay in DAG nodes.
2. Resources, reviews, and experiments become project records.
3. Runtime outputs artifact handles instead of large inline payloads.
4. Parameter sweeps belong to an experiment layer, not the workflow graph.
5. Branching is restricted to explicit router and gate nodes; loops stay out of the graph.

## Consequences

Keeping deterministic transforms inside DAG nodes preserves reproducibility, caching, and clear provenance for preprocessing and analysis. Project-level records for corpus views, dictionary overlays, review tasks, and experiment specs keep user-facing workflows auditable and backward-compatible with saved project state.

Artifact handles reduce manifest bloat, allow lazy preview loading in the UI, and keep packaging safe for large runs by moving bulky outputs into dedicated run artifacts. Restricting graph control flow to explicit router and gate nodes keeps the runtime portable and reviewable while reserving more advanced orchestration for a future experiment or workflow layer instead of turning the DAG into a general scripting engine.
