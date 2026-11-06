# Documentation claim auditor

Offline, deterministic, standard-library-only inspection of documentation about
ink transcription. Python 3.9 or later is required. No network, telemetry, model
execution, or file writes are performed.

## Usage

```sh
python3 -m pip install .
handwriting-recognition-claim-audit audit .
python3 -m handwriting_recognition_claim_audit audit . --json
handwriting-recognition-claim-audit audit . --verbose --ignore vendor/ --ignore examples/
handwriting-recognition-claim-audit audit . --fail-on medium
handwriting-recognition-claim-audit --version
```

The repository defaults to the current directory. Exit codes are 0 when no finding
reaches the threshold, 2 when one does, and 1 for usage or IO errors. The default
threshold is high. JSON emits a list with id, severity, path, verdict, message,
and phrases on each finding. Verbose scope and per-file decisions go to standard
error. Repeatable ignore prefixes match repository-relative paths.

## Scope and rules

Scans the root README and Markdown below docs. Claims in files under a tests
directory receive medium severity. All Python sources are inspected, excluding
version control, bytecode caches, virtual environments, and build output.
Each evidence route must be complete in one module. Imported aliases, simple
assigned aliases, and chained calls are supported. Local function and class
definitions shadow imported names. Unparseable modules supply no evidence.

Fenced code is excluded; inline code counts as prose. Exact, case-insensitive
substring matching uses no stemming or hyphen normalization. Denial spans are
removed first. Longest-first matching makes each occurrence match once under its
longest phrase. A claim without evidence is high severity; a denial contradicted
by evidence is high severity. A denial without evidence passes. Identifiers:

```text
documented-handwriting-recognition-claim-false
documented-no-handwriting-recognition-claim-false
```

## Differentiation

The following neighbors check printed text, describing an image, and assigning a
label to an image, respectively:

```text
ocr-claim-audit
image-captioning-claim-audit
classification-claim-audit
```

This tool checks decoding ink on the page: transcribing handwritten words rather
than printed text, an image description, or an image label. Those neighboring
capabilities alone do not establish the checked feature.

## Evidence and limitations

Static pattern matching is not semantic judgement. Exact phrases miss restatements.
A generic call on an unrelated object counts because the method name is shared:

```python
unrelated.read_handwriting()
```

Bare generic calls require a matching from-import. The following triple requires
processor and model construction plus generation on that model in one module.
It shows the checked feature is used, not that the transcriptions are correct:

```text
transformers.TrOCRProcessor + transformers.VisionEncoderDecoderModel + model.generate(...)
```

The following model requires construction plus generation or a direct instance
call; the next pair requires both calls in one module:

```text
transformers.AutoModelForVision2Seq + model.generate(...) or model(...)
kraken.lib.models.load_any + kraken.rpred.rpred
```

The pipeline below requires a call on its returned instance. Its model literal
alone is trusted without any network call or weight check:

```python
from transformers import pipeline
p = pipeline("image-to-text", model="...trocr...")
p(page)
```

Cloud document-read calls and generic printed-text OCR engines are deliberately
not counted because they read printed text as well as handwriting. Synthesis,
font rendering, signature verification, bare imports, strings, comments,
docstrings, subprocess commands, setup alone, and evidence split across modules
do not count. Control flow and runtime types are not evaluated.

The first three phrases below can describe a person reading handwritten notes;
the fourth can describe detecting that a document is handwritten rather than
transcribing its content. The auditor cannot distinguish those meanings:

```text
read handwriting
reads handwriting
reading handwriting
handwriting recognition
```

## Development

```sh
python3 -m unittest discover
python3 -m build
```

Distributed under the MIT license.
