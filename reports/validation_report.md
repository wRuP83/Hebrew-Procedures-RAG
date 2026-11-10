# Local validation

The local publication candidate was validated on November 10, 2026. These checks cover packaging, evidence integrity and notebook execution with a recorded-response replay; they are not a new live-model evaluation.

## Results

| Check | Result | Scope |
|---|---|---|
| Notebook format and syntax | PASS | nbformat schema and syntax for all non-magic code cells |
| High-level introductions | PASS | All 18 code cells have a short preceding section; outputs and execution counts are cleared |
| Embedded data consistency | PASS | Notebook data matches the public data file; five policy sections match baseline evidence contexts |
| Evidence preservation | PASS | Reconstructing the original historical JSON reproduces its recorded SHA-256; original fields are unchanged |
| Review totals | PASS | 18/19 base PASS after review; 2/4 conversation PASS against the stated contract |
| Core logic comparison | PASS | Retrieval, generation, rewriting, checks and judge definitions match the baseline; only the save function's report-state label differs |
| Content and sensitive-data scan | PASS | Public files checked for disallowed framing, private paths, email addresses and common secret patterns |
| Documentation navigation | PASS | Relative Markdown file links resolve within the package |
| Runtime replay | PASS | Real local embeddings, Chroma and reranking; 23 generation replies, 23 judge replies and four rewrites replayed from recorded evidence |
| Baseline comparison | PASS | Recorded answers, contexts, rounded hits, quality objects and rewrite checks matched the replayed execution |
| Resume behavior | PASS | Re-running completed evaluation loops made no additional replay API calls |
| Export and test isolation | PASS | Results and ZIP exported only in a temporary directory; the synthetic test credential was not persisted |

## Method

`tools/validate_release.py` performs structural, content, hash and consistency checks. Its `--runtime` mode executes the notebook in a temporary working directory with real retrieval models while replacing the Gemini and Colab interfaces with explicit local replay adapters.

The replay adapter matches the actual question, context and expected-check input to a historical record before returning that record's output. This validates the data flow and scoring without generating a new answer or writing synthetic results into the evidence snapshot.

Additional preparation checks compared the baseline and public function definitions, original and public policy sections, and all original evaluation fields. The public notebook changes are confined to high-level documentation, the synthetic-data header, output paths, display labels, notebook revision and a saved report-state label.

## What was not established

- **Live Gemini validation:** no new Gemini requests were made during preparation, and the public notebook was not run in a fresh Colab session with a real key.
- **Product fixes:** the known retrieval threshold, numeric-check and rewrite findings remain open; a successful validation run does not resolve them.
- **Security assurance:** the content scan is not a complete secrets audit or an authorization/prompt-injection penetration test.
- **Repeatability guarantees:** API availability, model revisions, hardware and transitive dependencies may change future results.
- **Third-party license clearance:** an inventory and scope notice are included, but a full third-party license audit remains separate.

## Re-run the checks

Structural and evidence checks:

```bash
python -m pip install -r requirements-dev.txt
python tools/validate_release.py
```

Full recorded-response replay with real local retrieval:

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python tools/validate_release.py --runtime
```

The second command may download model weights but does not require or consume a Gemini API key. Historical baseline results and review decisions remain separate from newly generated run artifacts.
