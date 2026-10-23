"""A WORKED EXAMPLE of a PII classifier. Not production code.

**Do not ship this.** It is here so the onboarding rehearsal exercises a real classifier path
instead of the deny-all default, and so you can see the shape of one. A regex list is not a
serious classifier: it will miss anything phrased unusually, and it has no notion of context.

What it does illustrate, and what you should keep:

* The *obligation* to classify is the platform's and cannot be switched off. What counts as
  prohibited is yours, and this file is where that judgement lives.
* Both the structured value and the free-text narrative are checked. An allowed topic is not a
  licence for the content carried under it, and the narrative is where a model is most likely to
  have smuggled something the value does not show.
* The refusal reason is a short code, never the matched text. Putting the matched text in the
  reason would write the thing you refused to store into a log line.
* Deny on doubt. The cost of storing a prescription in a brand-preference field is not
  symmetric with the cost of dropping one fact.
"""

from __future__ import annotations

import re

from memory_manager.extensions import ClassificationResult

#: Replace entirely. Yours will be longer, and probably will not be regexes.
_PROHIBITED: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")),
    ("phone", re.compile(r"\+?\d[\d\s().-]{8,}\d")),
    ("payment_card", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    ("government_id", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("health", re.compile(r"\b(diagnos\w*|prescri\w*|\d+\s?mg)\b", re.I)),
)


class SampleClassifier:
    """Refuses a value or narrative matching the domain's prohibited vocabulary."""

    def classify(self, fact, caller) -> ClassificationResult:
        for haystack in (str(fact.value), str(fact.text)):
            for label, pattern in _PROHIBITED:
                if pattern.search(haystack):
                    return ClassificationResult(allowed=False, reason=label)
        return ClassificationResult(allowed=True)
