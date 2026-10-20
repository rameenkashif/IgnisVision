# Urdu translation review

All Urdu strings are drafted by Claude and **need review by a fluent Urdu speaker** familiar with Rescue 1122 terminology (Q13 in `docs/DECISIONS.md`).

- Source of truth: `frontend/src/i18n/ur.json` (mirrors `en.json` key for key; a unit test enforces parity and placeholders).
- Status: **all keys `needs_review`** as of Phase 2.

## How to review

1. Open `ur.json` side by side with `en.json`.
2. Edit strings in place. Keep `{{placeholders}}` exactly as they are.
3. Points to check in particular:
   - Role names (`roles.*`): are "انسیڈنٹ کمانڈر" / "فیلڈ ریسپانڈر" the terms used in Rescue 1122, or are Urdu equivalents preferred?
   - Zone statuses (coming in Phase 3/4): safe / caution / unsafe / blocked / unclassified.
   - Spoken alerts (Phase 4): must be short, unambiguous and natural when read by a text-to-speech voice.
   - The disclaimer (`onboarding.steps.disclaimer`): must keep its meaning exactly.
4. When a section is approved, note it below.

## Reviewed sections

_None yet._
