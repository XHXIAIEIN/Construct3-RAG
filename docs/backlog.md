# Construct3-RAG Backlog

## Steal Patterns (from Orchestrator research)

### D7: Hybrid RAG Dual-Source Fusion
- **Source**: Tavily (R3), Orchestrator Round 3
- **Priority**: P1
- **Description**: Local vector DB + external search fusion. Combine Qdrant local results with live web search (Tavily/Brave) for queries where local docs are insufficient.
- **Implementation idea**: Query both sources in parallel, merge results with RRF (Reciprocal Rank Fusion), deduplicate by content hash, return top-K.
- **Dependencies**: Qdrant (already have), search API key (Tavily or Brave)
- **Status**: Pending
