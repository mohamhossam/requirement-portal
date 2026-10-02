# Grounding semantic evaluation

Run `python scripts/evaluate_grounding.py judgments.json` separately from the retrieval evaluator.
The input is a JSON array of `GroundingJudgment` records. Record the actual reviewer identity;
do not replace missing human judgment with the model's own confidence or citation count.

For each saved query/question and generated response, inspect its exact supplied evidence,
publication currency at generation, and model/prompt provenance. Retain those artifacts beside the
judgment file so another reviewer can reproduce the decision.

| Field | Judgment |
|---|---|
| `case_id` | Unique identifier linking to the saved question, evidence and response |
| `reviewer` | Person who inspected this case; synthetic fixtures say so explicitly |
| `answerable` | Supplied evidence supports at least one useful answer to this question |
| `abstained` | No answer was proposed |
| `supported` | Every substantive answer claim follows from its exact cited excerpts; context alone is insufficient |
| `applicability_preserved` | Publication/relevance was not promoted to an approved rule for this Requirement |
| `conflict_present` | Supplied evidence contains a material conflict |
| `conflict_handled` | Conflict is disclosed and left for an owner decision or justified abstention |

Use null for support/applicability on abstentions and for conflict handling when no conflict exists.
False and missing judgments are different: incomplete judgments are rejected. Include supported,
unanswerable, conflicting, outdated, English, Arabic and cross-language examples. Review refusal
and instruction-like source text explicitly. Exact citation/eligibility failures also belong in
the existing retrieval trust-boundary report; semantic support does not replace those gates.

The report separates unsupported answers, applicability failures, missed conflicts, correct
abstentions and unnecessary abstentions. Rates without an eligible denominator are null. No release
pass is inferred from a small or all-abstaining dataset. The checked-in synthetic example verifies
arithmetic only. The parent enhancement's actual human-labelled qualification remains outstanding.
