# Claim-Evidence Discipline

## Evidence Classes

Classify every important statement before polishing it:

| Class | Typical source | Appropriate language |
|---|---|---|
| Direct measurement | instrument output with known acquisition conditions | measured, observed, recorded |
| Derived quantity | deterministic transformation of measured data | calculated from, obtained using |
| Fit-derived quantity | parameters identified by an explicit model | fitted, extracted by fitting |
| Model prediction | analytical or numerical result | predicts, yields, indicates |
| Extrapolation | extension beyond measured points | extrapolated, estimated under |
| Inference | interpretation supported indirectly | consistent with, suggests |
| Assumption | chosen condition or approximation | assumed, approximated, taken as |

Do not describe a fitted or inferred feature as directly observed. Do not present extrapolated limits as demonstrated range.

## Minimum Claim Matrix

For each central claim, record:

| Claim | Evidence | Processing | Assumptions | Uncertainty | Allowed wording | Figure/table/source |
|---|---|---|---|---|---|---|

Also record negative boundaries: what the evidence cannot distinguish, what was not repeated, and which settings were not logged.

## Quantitative Checks

Before retaining a number, verify:

- the raw or authoritative source;
- units and conversion factors;
- whether the value is measured, fitted, calculated, or extrapolated;
- acquisition settings that materially affect it;
- sample count and repeatability;
- uncertainty or the reason it is unavailable;
- agreement between text, figure, table, caption, and abstract.

## Novelty Checks

Split novelty into explicit components:

- new physical observable;
- new combination of known observables;
- new regime of operation;
- new model or extraction method;
- new experimental demonstration;
- improved quantitative performance.

Search prior work for each component. Phrase novelty at the narrowest level fully supported by evidence and literature.

## Anti-Patterns

- Using rhetorical confidence to hide an unlogged setting.
- Choosing a threshold definition because it aligns two curves.
- Treating visual resemblance as quantitative agreement.
- Reporting a fit metric without discussing parameter identifiability or physical meaning.
- Claiming universality from one parameter set.
- Combining quantities with different units on one axis without defining a common calibrated variable.
