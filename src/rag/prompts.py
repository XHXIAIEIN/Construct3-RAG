"""
Prompt templates — re-exported from active locale.

Usage conventions (strongly recommended):
1) {context} is NOT a blob of concatenated text — it's a list of citable evidence blocks:
   [1] title: ...
       source: ...
       snippet: ...
   [2] ...

2) The model cites evidence block numbers in answers as [来源: 1] / [Source: 1].
3) If the information is not in the context, the model must say so — no fabrication.

These templates can be used with str.format() or LangChain PromptTemplate.
"""

from __future__ import annotations

# Re-export all prompt constants from active locale
from src.locale import (  # noqa: F401
    SYSTEM_MESSAGE, QA_PROMPT, STRICT_QA_PROMPT,
    LOW_RELEVANCE_PROMPT, NO_RESULTS_RESPONSE,
    LLM_UNAVAILABLE_RESPONSE, QDRANT_UNAVAILABLE_RESPONSE,
    LOW_CONFIDENCE_WARNING,
    EVENT_GENERATION_PROMPT, ROUTER_PROMPT,
    QUERY_REWRITE_PROMPT, QUERY_DECOMPOSITION_PROMPT,
    SELF_REFLECTION_PROMPT, ANSWER_VERIFICATION_PROMPT,
    CLIPBOARD_FORMAT_REFERENCE, EVENT_JSON_GENERATION_PROMPT,
    JS_HINT_FOOTER, JS_INCLUDE_INSTRUCTION, CONTEXT_FORMAT_GUIDE,
    LOOKUP_CLASSIFY_PROMPT,
    CLIPBOARD_CONTEXT_HEADER, CLIPBOARD_DEFAULT_QUERY,
    SEMANTIC_DECOMPOSE_PROMPT,
)
