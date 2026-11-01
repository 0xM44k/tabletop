# Research record (2026-10-26)

Method: web searches plus two page fetches. Search result pages gave titles only.

## Observed

- [Security Scientist, tabletop design for small teams](https://www.securityscientist.net/blog/12-questions-and-answers-about-tabletop-exercise-design-for-small-teams-2/) (fetched; a vendor-style blog, so treat as opinion): include IT, Legal, Management and PR; the facilitator acts as a referee who asks probing questions rather than giving answers; keep it blameless; document every gap; write an after-action report with a named owner for each fix; map scenarios to your most critical systems and scale them to your resources. It gives no duration or inject count.
- [Paper on the INJECT Exercise Platform (arXiv 2404.10988)](https://arxiv.org/html/2404.10988v1) (fetched): paper-based tabletop exercises are hard to evaluate manually and feedback is slow; the open-source INJECT platform defines exercises in YAML with simulated tools and milestone tracking and logs team actions. The study was one course and one exercise, small cohorts, no control group, and did not measure learning gains.
- A search also surfaced commercial tabletop products and an open-source threat-simulation platform; I did not open them and make no comparison.

## Gap targeted

INJECT-style platforms are built for evaluating many teams in a course. A small team wanting a practical session has to write scenarios from scratch. tabletop is the opposite end: a zero-install, single-file facilitator page generated from a short JSON model of *your* systems, with names, data classes and dependencies filled into the injects and extra questions that react to which controls you say you have. It does not simulate tools or score anyone.

## Honest limits of the content

- Scenario text is generic incident-response practice that I wrote for this tool. It is not mapped to MITRE ATT&CK or any standard and has **not been reviewed by an incident-response professional**. Treat it as a starting structure and edit `catalog.json`.
- The model-aware part is simple: placeholders, a primary-asset choice (most data classes, then most connections), and controls-present/missing questions. It does not infer attack paths.
- Nothing here was tested with a real team in a real exercise.
