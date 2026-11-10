# Hebrew Procedures RAG

A Hebrew-language RAG prototype for answering questions from synthetic insurance procedures, with explicit source citations and a QA-oriented evaluation workflow. It combines semantic retrieval, cross-encoder reranking, Gemini generation, deterministic checks and a structured LLM judge.

[עברית](README.he.md) · [Notebook](notebooks/procedures_rag.ipynb) · [Evaluation report, Hebrew](reports/evaluation_report.md) · [Recorded results](results/evaluation_results.json) · [Review decisions](results/review_decisions.json)

## Why this project

Finding a relevant document does not guarantee a correct answer. This project examines where failures occur: retrieval filtering, query rewriting, response generation or the evaluation checks themselves.

The repository is centered on a self-contained Colab notebook and an evidence-based evaluation report. It is a prototype, not a production service, medical advice or an insurance recommendation.

## Architecture

```text
5 synthetic policy documents
  → Multilingual embeddings
  → Chroma candidate retrieval with audience metadata
  → Cross-encoder reranking and threshold filtering
  → Retrieved context + Gemini
  → Citation / numeric checks + structured LLM judge
  → Recorded evidence + separate review decisions
```

The conversation path additionally rewrites follow-up queries before retrieval. An empty-context model probe is recorded separately from the pipeline's hard-coded refusal, so the two cannot be mistaken for the same behavior.

## Baseline evaluation

The recorded run is dated November 9, 2026. These figures describe this small, fixed evaluation set only; they are not an estimate of general system accuracy.

| Evaluation group | Cases | Recorded automatic result | Result after assistant-assisted review |
|---|---:|---|---|
| Base questions | 19 | 17 PASS_CANDIDATE, 2 FAIL | 18 PASS, 1 FAIL |
| Conversation scenarios | 4 | 2 PASS_CANDIDATE, 2 FAIL | 2 PASS, 2 FAIL against the rewrite contract |

The base set contains 14 answerable questions and five questions without an answer in the corpus. Thirteen answerable questions succeeded, and all five unanswerable questions received the expected refusal.

### Findings

- **Retrieval threshold:** a cancellation document ranked first but was filtered out, causing a refusal despite an answer existing in the corpus.
- **Numeric-check false positive:** a comma following a time was included in a numeric token; the answer was correct, but the automated check failed.
- **Topic-switch rewriting:** a standalone service-hours question was rewritten into a question about a nonexistent dedicated appeals hotline.
- **Ambiguous input:** one short follow-up failed the exact-text rewrite contract, but the intended meaning remains ambiguous and is not presented as a proven intent hallucination.

These findings are intentionally retained. This publication candidate changes presentation and packaging, not the retrieval algorithm, prompts, threshold or evaluation logic.

## Run in Google Colab

1. Download `notebooks/procedures_rag.ipynb`.
2. In Colab, select **File → Upload notebook**.
3. Create or enable a Secret named `GEMINI_API_KEY` and grant the notebook access.
4. Run the cells in order. If dependency installation requests a runtime restart, restart and continue from the imports cell.
5. Download the generated results archive before resetting the runtime.

The notebook embeds the synthetic data and creates the index from scratch. Each runner supplies their own API key; a complete run makes 50 model requests before retries, and quota or billing depends on that runner's account.

New results are written to `artifacts/current_run/`. They do not overwrite the historical snapshot in `results/`, and the snapshot must not be used as a resume checkpoint for the public notebook.

A direct repository-to-Colab launch link can be added once an actual repository URL exists. Colab supports loading notebooks from GitHub, while GitHub itself renders notebooks statically ([Colab documentation](https://research.google.com/colaboratory/faq.html), [GitHub documentation](https://docs.github.com/en/repositories/working-with-files/using-files/working-with-non-code-files)).

## Stack and reproducibility

- **Embedding model:** `paraphrase-multilingual-MiniLM-L12-v2`.
- **Reranker:** `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`.
- **Vector store:** Chroma, cosine distance.
- **Generation and judge:** `gemini-3.8-flash` through the Interactions API.
- **Evaluation schema:** Pydantic models for claims, evidence and verdicts.
- **Configuration:** five candidates, up to three context documents, reranker score strictly greater than `-2.0`.

Direct dependencies are pinned in `requirements.txt`; this is not a full lockfile for all transitive dependencies or model revisions. Live model output may differ across runs, and model availability and account access must be checked when running.

The integration follows Google's [API quickstart](https://ai.google.dev/gemini-api/docs/quickstart), [system-instruction documentation](https://ai.google.dev/gemini-api/docs/text-generation) and [structured-output documentation](https://ai.google.dev/gemini-api/docs/structured-output).

## Local validation

For structural and evidence checks without a model request:

```bash
python -m pip install -r requirements-dev.txt
python tools/validate_release.py
```

For full notebook-flow validation with real local retrieval and a mocked Gemini/Colab interface:

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python tools/validate_release.py --runtime
```

Runtime validation may download embedding and reranker weights. Mocked responses are used only in a temporary test directory and are never merged into the recorded evaluation snapshot.

See [validation results](reports/validation_report.md) for the checks actually performed. Passing packaging checks does not mean the documented product bugs have been fixed.

## Limitations and evidence integrity

- **Small evaluation:** one baseline run, five short documents and no production traffic.
- **Known evaluation gaps:** the numeric check is lexical, the writer and judge use the same model, and rewrite fidelity is not yet scored independently end to end.
- **Refusal coverage:** the unanswerable examples had empty retrieved context; robustness against misleading, nonempty context was not established.
- **Security scope:** audience metadata filtering is implemented, but comprehensive authorization, adversarial or prompt-injection testing is not claimed.
- **Historical evidence:** baseline records remain unchanged; publication metadata is added separately, and later review decisions are stored in their own file.
- **Document header:** the public document has a reworded header but identical policy sections. Its hash differs from the original run document; both hashes are recorded, not conflated.

## Files and licensing

`notebooks/` contains the runnable prototype, `data/` the synthetic procedures, `reports/` the evaluation and validation reports, and `results/` the baseline evidence and review decisions. `artifacts/` is reserved for new local runs and is excluded from version control.

The MIT license applies to original project code only. Third-party libraries, model weights and hosted APIs are not relicensed by this repository; see [third-party notices](THIRD_PARTY_NOTICES.md).
