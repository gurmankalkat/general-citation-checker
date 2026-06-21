# Findings

## Comparison table

Eval run on a 60-sentence gold set. The set contains 13 non-claims, 20 correct factual claims labeled `supported`, and 27 wrong claims labeled `contradicted`. The most important metric is the false positive rate on `supported` verdicts, which counts how often the pipeline confidently validates a claim that is actually wrong.

| Metric | Parallel | Exa |
|---|---|---|
| Detection precision | 1.00 | 1.00 |
| Detection recall | 1.00 | 1.00 |
| Detection F1 | 1.00 | 1.00 |
| Verdict accuracy | 0.94 | 0.91 |
| FP rate (supported / wrong) | 0.07 | 0.11 |
| Retrieval calls | 47 | 47 |
| Estimated cost (USD) | $1.18 | $0.99 |

Detection was perfect across the board. Every non-claim was skipped. Every claim was detected. The difference between the two providers shows up entirely in grading.

---

## What held up

The straightforward cases worked well. Wrong founding years, wrong state counts, wrong delivery numbers: both providers found authoritative sources and the grader correctly called them contradicted with a correction. The 40 founding-year and round-number claims in the gold set were handled cleanly by both providers.

Claims with unambiguous, widely documented correct answers were almost never mislabeled. The pipeline is well-suited to the case where the wrong claim is plausible but the correct fact is not in dispute.

---

## Where each provider failed

### Parallel failures (3 of 47 graded claims)

**id=43: "Google holds more than 90% of the global search market."**
Gold: `contradicted`. Parallel returned: `supported`.

This is the hardest case in the gold set. Google's market share has hovered in the high 80s to low 90s percent range depending on the reporting period and source. Parallel returned sources citing StatCounter or similar data that puts the figure above 90% in some windows, and the grader accepted them. The claim is wrong as a flat assertion but the evidence is genuinely mixed. Parallel found the evidence that confirmed the claim rather than the evidence that contradicted it.

**id=54: "Bitcoin was created by a person named Satoshi Nakamoto."**
Gold: `contradicted`. Parallel returned: `supported`.

Satoshi Nakamoto is a pseudonym. The identity of the actual creator or creators is unknown. Most web sources treat Satoshi as a person without qualification, and Parallel returned those sources. The grader had no reason to doubt the framing. This is a case where the claim is technically wrong in a way that requires understanding the context rather than finding a contradicting data point.

**id=57: "There are 8 billion people on Earth."**
Gold: `supported`. Parallel returned: `contradicted`.
Correction produced: "There are approximately 8.3 billion people on Earth."

World population passed 8 billion in late 2022 and continues to rise. The claim is accurate as a round approximation. Both Parallel and Exa got this wrong in the same direction: they found current estimates near 8.3 billion and the grader treated the round number as a factual error rather than a reasonable approximation. This is a grader failure, not a retrieval failure. The prompt does not give the grader guidance on how to handle approximate quantities, and it defaulted to strict numerical comparison.

### Exa failures (4 of 47 graded claims)

Exa made all three of the same mistakes as Parallel above, plus one additional false support.

**id=48: "Mount Everest is the tallest mountain on Earth."**
Gold: `contradicted`. Exa returned: `supported`.

The distinction is between highest (above sea level) and tallest (base to peak). Measured base to peak, Mauna Kea is taller. Exa returned Wikipedia-style sources that describe Everest as the world's highest mountain, and the grader accepted those as support for the tallest claim without catching the distinction. Parallel returned sources that mentioned the Mauna Kea comparison and the grader correctly called the claim contradicted.

This is the clearest example in the eval of Parallel and Exa returning meaningfully different evidence for the same query. Exa surfaced the common framing. Parallel surfaced a more technical source that drew the height versus elevation distinction.

---

## Honest account of where Parallel surprised me

The headline result, a false positive rate of 0.07 versus 0.11, is the correct summary. But it deserves some unpacking.

Parallel was more conservative in a way that turned out to be the right default for a citation tool. It found the Mauna Kea comparison for id=48 where Exa did not. In a separate run on `sample.txt` outside the gold set, Parallel correctly contradicted "Apple was founded in Cupertino, California" (the correct location is Los Altos) while Exa returned the Wikipedia article describing Cupertino as Apple's current headquarters and called the claim supported.

But Parallel surprised me in the opposite direction on one case during an intermediate eval run. The claim "Larry Page and Sergey Brin were PhD students when they founded Google" (id=42, gold: `supported`) was called `contradicted` by Parallel with the correction that Page and Brin were enrolled in a doctoral program but took a leave of absence before completing their degrees. That correction is technically accurate. The gold label says the claim is supported. Parallel's grader found a real nuance and applied it, which produced a wrong verdict by the eval's measure. Exa called the same claim supported without comment.

Whether Parallel was right or wrong there depends on how you define "PhD students." If the gold label is correct, Parallel was overly pedantic. If Parallel's reading is correct, the gold label is too loose. That ambiguity resolved in the 60-sentence run when Parallel labeled id=42 correctly, possibly because the larger document context changed how the detection layer phrased the search query.

The cost difference is real. Exa cost $0.99 against Parallel's $1.18 for the same 47 retrieval calls. Parallel's lower FP rate costs roughly 19 cents per document at this scale. Whether that is worth it depends on the application. A pipeline that surfaces results to an editor who will read them anyway can tolerate a higher FP rate. A pipeline that auto-publishes corrections cannot.

The two failure modes the providers shared, the Google market share case and the Bitcoin pseudonym case, are genuinely hard. The Google case fails because the evidence is ambiguous and sources exist on both sides. The Bitcoin case fails because no web source contradicts the pseudonym framing directly; they all just accept it. Neither of these is a retrieval failure. The evidence returned was reasonable. The grader had no basis to doubt it. Improving these cases requires either a more skeptical grading prompt or an additional verification step that explicitly checks whether the claim's framing (a real person versus a pseudonym) is accurate before looking for supporting facts.
