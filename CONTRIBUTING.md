# Contributing

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run tests

```bash
pytest tests/ -q
```

## Lint / typecheck

```bash
ruff check src/socialdrop tests
mypy src/socialdrop tests
```

## Frontend

```bash
cd web
npm install
npm run lint
npm run build
```

## Commit messages

- Use present tense, imperative mood
- Reference issue numbers when possible

## Code of conduct

Be respectful. No harassment, no trolling.
