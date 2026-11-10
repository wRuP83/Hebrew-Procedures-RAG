# Third-party components and usage boundaries

The MIT license in this folder covers original project code only. It does not grant rights to third-party software, model weights, hosted services, trademarks or materials supplied independently.

## Components used

- **Python packages:** google-genai, chromadb, sentence-transformers, pydantic and their transitive dependencies. nbformat is used for local validation.
- **Downloaded models:** paraphrase-multilingual-MiniLM-L12-v2 and cross-encoder/mmarco-mMiniLMv2-L12-H384-v1.
- **Hosted API:** Google Gemini, accessed with each runner's own credentials and account.

Package distributions, model weights and credentials are not bundled in the source package. Before redistribution or deployment, review the actual package and model licenses and the provider's current terms; this file is an inventory, not a completed third-party license audit.

## Data and results

The procedure document describes a fictional company and synthetic policies. It is provided for technical demonstration only and is not medical or insurance advice.

The recorded outputs are evidence from one evaluation run. Their inclusion does not imply guaranteed future model behavior, production readiness or endorsement by a service provider.
