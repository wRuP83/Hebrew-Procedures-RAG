"""Validate packaging and evidence. Optional execution replays recorded API outputs."""
import argparse
import ast
import contextlib
import hashlib
import io
import json
import linecache
import os
from pathlib import Path
import re
import sys
import tempfile
import types

import nbformat

ROOT = Path(__file__).resolve().parents[1]

def digest(data):
    return hashlib.sha256(data).hexdigest()

def read_json(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))

def static_checks():
    notebook = nbformat.read(ROOT / "notebooks/procedures_rag.ipynb", as_version=4)
    nbformat.validate(notebook)
    codes = []
    for index, cell in enumerate(notebook.cells):
        if cell.cell_type != "code":
            continue
        assert index > 0 and notebook.cells[index - 1].cell_type == "markdown"
        assert not cell.outputs and cell.execution_count is None
        assert len(notebook.cells[index - 1].source.splitlines()) <= 5
        codes.append(cell.source)
        if not cell.source.startswith("%pip"):
            compile(cell.source, f"notebook_cell_{index}", "exec")
    assert len(codes) == 18
    assert sum(s.startswith("%pip") for s in codes) == 1

    synthetic_data = (ROOT / "data/synthetic_procedures.md").read_text(encoding="utf-8")
    embedded_data = None
    for source in codes:
        if source.startswith("%"):
            continue
        for node in ast.parse(source).body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "PROCEDURES" for target in node.targets
            ):
                embedded_data = ast.literal_eval(node.value)
    assert embedded_data == synthetic_data
    sections = synthetic_data.split("## ")[1:]
    assert len(sections) == 5
    documents = {}
    for section in sections:
        value = section.strip()
        documents[re.match(r"נוהל (\d+\.\d+)", value).group(1)] = value

    snapshot = read_json("results/evaluation_results.json")
    reviews = read_json("results/review_decisions.json")
    manifest = read_json("results/publication_manifest.json")
    metadata = snapshot["publication_metadata"]
    historical = dict(snapshot)
    historical.pop("publication_metadata")
    reconstructed = json.dumps(historical, ensure_ascii=False, indent=2).encode()
    assert digest(reconstructed) == metadata["source_results_sha256"]
    assert metadata["public_document_sha256"] == digest(synthetic_data.encode())
    assert metadata["original_run_document_sha256"] == snapshot["doc_sha256"]
    assert manifest["source_results_sha256"] == metadata["source_results_sha256"]
    assert manifest["public_notebook_sha256"] == digest(
        (ROOT / "notebooks/procedures_rag.ipynb").read_bytes()
    )
    assert len(snapshot["base"]) == 19 and len(snapshot["followups"]) == 4
    assert len(reviews["decisions"]) == 23
    assert sum(r["quality"]["auto_status"] == "FAIL" for r in snapshot["base"].values()) == 2
    assert sum(
        r["review_status"] == "PASS" and r["group"] == "base"
        for r in reviews["decisions"].values()
    ) == 18
    assert sum(
        r["review_status"] == "PASS" and r["group"] == "followups"
        for r in reviews["decisions"].values()
    ) == 2
    for group in ("base", "followups"):
        for key, row in snapshot[group].items():
            result, quality = row["result"], row["quality"]
            assert result["generation_called"] is True and not row.get("error")
            assert quality["final_status"] == "PENDING_REVIEW"
            assert reviews["decisions"][key]["auto_status_recorded"] == quality["auto_status"]
            expected_context = "\n\n".join(
                f"[{doc_id}] {documents[doc_id]}" for doc_id, score in result["hits"]
            )
            assert result["context"] == expected_context
    assert snapshot["base"]["NEW-04"]["quality"]["numbers"]["unsupported"] == ["00,"]
    assert reviews["decisions"]["NEW-04"]["review_status"] == "PASS"
    assert reviews["decisions"]["NEW-03"]["review_status"] == "FAIL"

    # Numeric rates in the synthetic policies are legitimate domain content.
    forbidden = [
        re.compile(r"\u05e7\u05d5\u05e8\u05e1"),
        re.compile(r"(?<!\w)\u05e9\u05d9\u05e2\u05d5\u05e8\s*[-:#]?\s*\d+\b(?!\s*%)"),
        re.compile(r"\b(?:c[o]urse|less[o]n)\b", re.I),
        re.compile(r"\u05dc\u05d5\u05de\u05d3"),
        re.compile(r"/h[o]me/|ppl[x]://|\.perplexit[y]/|/computer/task[s]/"),
        re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
        re.compile(r"\bgh[pousr]_[0-9A-Za-z]{20,}\b"),
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ]
    scanned = 0
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in {".git", "__pycache__", "artifacts"} for part in path.parts):
            continue
        content = path.read_text(encoding="utf-8")
        for pattern in forbidden:
            assert not pattern.search(content), f"Content scan failed: {path.relative_to(ROOT)}"
        if path.suffix == ".md":
            for target in re.findall(r"\]\(([^)]+)\)", content):
                if "://" in target or target.startswith("#"):
                    continue
                assert (path.parent / target.split("#")[0]).exists(), f"Missing file: {target}"
        scanned += 1
    print(f"PASS: notebook schema, 18 code cells, high-level introductions, {scanned} files scanned.")
    print("PASS: historical records, hashes, 19+4 cases, policy contexts and review totals.")
    return notebook, snapshot

def runtime_checks(notebook, snapshot):
    # Retrieval is real; Gemini/Colab replies are replayed from the evidence snapshot.
    from google import genai

    rows = list(snapshot["base"].values()) + list(snapshot["followups"].values())
    counts = {"generation": 0, "judge": 0, "rewrite": 0}

    class ReplayInteractions:
        def create(self, **kwargs):
            prompt = kwargs["input"]
            if "response_format" in kwargs:
                counts["judge"] += 1
                matches = [
                    row for row in rows
                    if prompt == (
                        f"<קונטקסט>\n{row['result']['context']}\n</קונטקסט>\n"
                        f"שאלה: {row['result']['search_q']}\nתשובה: {row['result']['answer']}\n"
                        f"ציפיית בדיקה: {row['case']['expected']}"
                    )
                ]
                assert len(matches) == 1, "Replay judge input does not match baseline evidence"
                verdict = matches[0]["quality"]["judge"]
                text = json.dumps({
                    key: verdict[key] for key in
                    ["claims", "refused", "relevant", "complete", "format_ok", "reason"]
                }, ensure_ascii=False)
            elif kwargs["system_instruction"].startswith("שכתב"):
                counts["rewrite"] += 1
                matches = [
                    row for row in snapshot["followups"].values()
                    if prompt == (
                        "\n".join(f"משתמש: {q}" for q in row["case"]["history"][-3:])
                        + "\nשאלת המשך: " + row["case"]["q"]
                    )
                ]
                assert len(matches) == 1
                text = matches[0]["rewritten"]
            else:
                counts["generation"] += 1
                matches = [
                    row for row in rows
                    if prompt == (
                        f"<נהלים>\n{row['result']['context']}\n</נהלים>\n\n"
                        f"שאלה: {row['result']['search_q']}"
                    )
                ]
                assert len(matches) == 1, "Replay generation input does not match baseline evidence"
                result = matches[0]["result"]
                text = result["empty_context_probe"] if not result["hits"] else result["answer"]
            return types.SimpleNamespace(output_text=text)

    colab = types.ModuleType("google.colab")
    colab.userdata = types.SimpleNamespace(get=lambda name: "LOCAL_TEST_ONLY")
    colab.files = types.SimpleNamespace(download=lambda path: None)
    previous_colab = sys.modules.get("google.colab")
    original_client = genai.Client
    sys.modules["google.colab"] = colab
    genai.Client = lambda **kwargs: types.SimpleNamespace(interactions=ReplayInteractions())
    original_cwd = Path.cwd()
    codes = [cell.source for cell in notebook.cells if cell.cell_type == "code"]
    scope = {"__name__": "__main__"}
    def artifact_fingerprints():
        return {
            str(path.relative_to(ROOT)): digest(path.read_bytes())
            for path in (ROOT / "artifacts").rglob("*") if path.is_file()
        }
    artifacts_before = artifact_fingerprints()

    def execute(index, source, directory):
        name = str(directory / f"execution_cell_{index}.py")
        linecache.cache[name] = (len(source), None, source.splitlines(True), name)
        exec(compile(source, name, "exec"), scope)

    try:
        with tempfile.TemporaryDirectory(prefix="procedures-rag-validation-") as temporary:
            directory = Path(temporary)
            os.chdir(directory)
            with contextlib.redirect_stdout(io.StringIO()):
                for index, source in enumerate(codes):
                    if not source.startswith("%"):
                        execute(index, source, directory)
            assert counts == {"generation": 23, "judge": 23, "rewrite": 4}, counts
            assert len(scope["base"]) == 19 and len(scope["followups"]) == 4
            for group in ("base", "followups"):
                for key, actual in scope[group].items():
                    expected = snapshot[group][key]
                    assert actual["quality"] == expected["quality"], key
                    for field in ["answer", "answer_source", "context", "hits", "empty_context_probe"]:
                        normalized = json.loads(json.dumps(actual["result"][field], ensure_ascii=False))
                        assert normalized == expected["result"][field], (key, field)
                    if group == "followups":
                        assert actual["rewritten"] == expected["rewritten"]
                        assert actual["unchanged_check"] == expected["unchanged_check"]
            before = dict(counts)
            with contextlib.redirect_stdout(io.StringIO()):
                for index, source in enumerate(codes):
                    if source.startswith("for case in CASES:") or source.startswith("rewrite_signature ="):
                        execute(index, source, directory)
            assert counts == before, "Resume issued duplicate API requests"
            result_path = directory / "artifacts/current_run/answers.json"
            assert result_path.exists()
            assert "LOCAL_TEST_ONLY" not in result_path.read_text(encoding="utf-8")
            assert (directory / "rag-evaluation-results.zip").exists()
            assert artifact_fingerprints() == artifacts_before, "Tests changed existing run artifacts"
            assert scope["numbers_faithful"](
                snapshot["base"]["NEW-04"]["result"]["answer"],
                snapshot["base"]["NEW-04"]["result"]["context"],
            )["unsupported"] == ["00,"]
    finally:
        os.chdir(original_cwd)
        genai.Client = original_client
        if previous_colab is None:
            sys.modules.pop("google.colab", None)
        else:
            sys.modules["google.colab"] = previous_colab
    print("PASS: real retrieval; 50 replayed API operations; baseline quality and context preserved.")
    print("PASS: checkpoint resume without duplicate calls; export; test secret not persisted.")
    print("LIVE GEMINI CALLS: 0. Replayed outputs are not a new model evaluation.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", action="store_true", help="Run real retrieval with recorded API replay")
    args = parser.parse_args()
    notebook, snapshot = static_checks()
    if args.runtime:
        runtime_checks(notebook, snapshot)
