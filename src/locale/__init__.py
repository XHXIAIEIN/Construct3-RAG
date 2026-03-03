"""Locale package — language-aware exports."""

from src.config import UI_LANGUAGE

if UI_LANGUAGE == "en":
    from src.locale.en.prompts import *    # noqa: F401,F403
    from src.locale.en.messages import *   # noqa: F401,F403
else:
    from src.locale.zh.prompts import *    # noqa: F401,F403
    from src.locale.zh.messages import *   # noqa: F401,F403

# keywords are always Chinese (NLP tokenization, not UI-language-dependent)
from src.locale.keywords import (         # noqa: F401
    ACE_INTENT_KEYWORDS, ACE_TYPE_ALIASES, ZH_STOP_WORDS,
    HOWTO_SKIP_WORDS, ZH_PARTICLES, INTENT_TEMPLATES,
    COMPLEXITY_INDICATORS, CODE_GENERATION_KEYWORDS,
)
