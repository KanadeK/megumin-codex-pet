# Contributing

Issues and code contributions to PetDiff are welcome.

## Before a pull request

```bash
python -m pip install -e ".[dev]"
ruff check .
mypy src
pytest --cov=megumin_pet --cov-report=term-missing
python -m build
```

When changing `pet/`, also run the strict release check and attach the generated
PetDiff HTML report plus animation previews.

## Asset rules

- Do not submit official or traced art, screenshots, logos, dialogue, audio, or
  extracted game/anime assets.
- Do not use a third-party image as an image-generation input unless its license
  and provenance are documented and compatible.
- Generate or repair coherent rows, not isolated mismatched cells.
- Preserve the 8×11 v2 contract and the 16 clockwise look directions.
- State which generator/tool produced new art and retain the hatch QA evidence.

By contributing code or documentation, you agree that your contribution is
licensed under MIT. That statement does not claim or convey rights in
third-party characters.

## Commit hygiene

Use focused commits and do not add `Co-authored-by` trailers for people who did
not author the change. Never commit API keys, cookies, generated virtual
environments, or user Codex configuration.
