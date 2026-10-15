# Reproduce the reviewed local fixture smoke

Observed environment on 2026-10-16: Windows, Python `3.13.2`, Git
`2.47.0.windows.2`. The source execution path uses the Python standard library;
`setuptools>=68` is only a build requirement in `pyproject.toml`. Run from this
working tree without package installation:

```powershell
$env:PYTHONPATH='src'
$env:PYTHONDONTWRITEBYTECODE='1'
python -B scripts/phase1_preflight.py
python -B -m unittest discover -s tests -t .
python -B scripts/phase5_evaluate.py
python -B scripts/phase5_validate.py
$manifest = (Get-ChildItem evals/results/raw/phase5-fixture-smoke-v5/demo-parser-001/rewindcoder_full/seed-0 -Recurse -Filter manifest.json | Where-Object { $_.Directory.Name -like 'run-*' } | Select-Object -First 1 -ExpandProperty FullName)
python -B scripts/phase5_replay.py $manifest
python -B scripts/phase4_demo.py
git diff --check
```

The runner only accepts three reviewed local fixture templates; it never
accepts an arbitrary repository URL. It creates disposable workspaces under
ignored `artifacts/runs/`. Existing matrix cells resume only with matching
hashes. Raw `v1`–`v4` runner-development artifacts are retained but excluded from
the `v5` summary. The raw `v5` tree and summary must be copied with the exact
source state if the experiment is moved to another machine.

This is an environment recipe, not a fresh-clone guarantee. The working tree
contains Phase 2–5 code absent from HEAD; a fresh clone of HEAD lacks this
runner. Docker Engine was not available, so there is no verified container
image or arbitrary-repository sandbox. A source revision and clean-clone run
are release gates, not properties inferred from a source hash.
