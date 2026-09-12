# Evidence Retrieval Decision

## Decision

Keep the existing deterministic ID-based retrieval. Do not add keyword search, BM25, embeddings, a vector database, or a RAG framework.

The dataset already supplies exact `user_id`, `request_id`, and `related_event_id` relationships. Adding semantic retrieval would not recover an identified missing record and would expand the untrusted-evidence surface unnecessarily.

## Dataset measurements

| Measure | Result |
|---|---:|
| Evaluation requests | 250 |
| Messages | 215 |
| Images | 16 |
| Financial events | 25,342 |
| Message length, mean / p95 / max | 251 / 303 / 330 characters |
| Messages with request link only | 100 |
| Messages with request and event links | 28 |
| Messages with event link only | 11 |
| Messages without request/event link | 76 |
| Images with request and event links | 16 |
| Users with exactly one request | 275 of 275 |

The 76 messages without a request or event link are still directly scoped by their valid `user_id`. Since every user has exactly one request, this is an exact deterministic association rather than a semantic-retrieval problem.

## Retrieval quality comparison

The source files contain no separate relevance labels, so retrieval quality is measured against their explicit relationships and user scope.

| Retrieval approach | Same-user message recall | Image recall | Largest evaluation-request context | Result |
|---|---:|---:|---:|---|
| No retrieval | 0% | 0% | 0 | Insufficient |
| Existing direct IDs (`user_id`, `request_id`, `related_event_id`) | 100% (0 misses) | 100% | 1 message, 1 image | Sufficient |
| Keyword/BM25/embedding retrieval | No measurable missing source to recover | No measurable missing source to recover | Larger, less constrained candidate set | Not justified |

Direct context retrieval across the 250 evaluation requests returns 198 messages and 11 images in total. The maximum context for one request is one message and one image. All 215 message user IDs, all populated message request/event IDs, and all image user/request/event IDs resolve to valid source records.

## Security and correctness implications

Direct joins preserve provenance and the current evidence policy: messages and images are processed only within the owning user's request context, image facts must match their linked event, and untrusted content cannot become a cross-user or unrelated-event fact. Semantic retrieval would need a new relevance policy and would create more opportunities for irrelevant or adversarial text to enter the evidence path.

The existing [evaluation report](evaluation_report.md) records zero failures from the implemented full-output deterministic checks. That result does not establish hidden-label correctness.

## Implemented outcome

No retrieval code was added because the measured direct-join baseline has complete source-scope recall and a tiny candidate set. The current indexes in `code/buy_or_wait/loaders.py` remain the smallest appropriate mechanism.
