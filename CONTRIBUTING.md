# Contributing to RapidRMF

Thanks for your interest in contributing to RapidRMF! This guide follows a streamlined, contributor-first flow (inspired by the Null Terminal style) while keeping RapidRMF specifics.

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [Contributor Agreement & Ownership](#contributor-agreement--ownership)
- [Getting Started](#getting-started)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Review Process](#review-process)
- [Release Process](#release-process)
- [Getting Help](#getting-help)
- [Recognition](#recognition)

---

## Code of Conduct
Be respectful, inclusive, and constructive. We are building something important together—keep interactions positive and focused on making RapidRMF better.

---

## Contributor Agreement & Ownership
This project is licensed under Apache-2.0. By submitting a contribution to RapidRMF, you agree your contribution is provided under the Apache-2.0 license and assign the project the rights below:

1) **Project Ownership**
- All contributions become the property of RapidRMF and its maintaining organization
- The project retains exclusive rights to use, modify, distribute, and sublicense contributions

2) **License Grant**
- You grant RapidRMF a perpetual, worldwide, non-exclusive, royalty-free, irrevocable license to use, reproduce, modify, and distribute your contributions
- Contributions are licensed under the same license as RapidRMF

3) **Intellectual Property Warranty**
- You own or have authority to grant the rights to your contribution
- Your contribution does not infringe any third-party IP
- You are not bound by agreements that conflict with contributing here

4) **Contributor Attribution**
- Contributors are credited in commit history
- A CONTRIBUTORS file may be used at project discretion

**Corporate Contributors**
- You confirm you have authority to contribute on behalf of your organization
- Your organization grants the same rights and warranties above
- Organizations may sign a Corporate CLA if required by governance

---

## Getting Started

### Prerequisites
- Python 3.14+
- Git
- Virtual environment (recommended)
- Pip (for installing dependencies)

### Development Setup
```bash
# Clone the repository
git clone https://github.com/your-org/RapidRMF.git
cd RapidRMF

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate (or use: py -3.14 -m venv .venv)

# Install dependencies
pip install -r requirements-prod.txt
pip install -r requirements-dev.txt

# Run the CLI (example)
python -m rapidrmf --help

# Run tests
pytest tests/ -q
```

---

## How to Contribute

### Reporting Bugs
- Check existing issues to avoid duplicates
- Use the bug report template
- Include: RapidRMF version, Python version, OS, steps to reproduce, expected vs actual behavior, relevant logs/screenshots

### Suggesting Features
- Check existing issues/discussions first
- Describe the use case clearly
- Explain why current features do not solve it
- Propose an implementation idea if possible

### Submitting Code
1) **Fork and Branch**
```bash
git checkout -b feature/your-feature-name   # new feature
git checkout -b fix/issue-123               # bug fix
git checkout -b docs/update-readme          # docs change
git checkout -b refactor/collector-common   # refactor
git checkout -b test/add-storage-coverage   # tests
```

2) **Make Changes**
- Keep changes focused and scoped
- Follow coding standards below
- Commit often with clear messages

3) **Test Your Changes**
```bash
# Run all tests
pytest tests/ -q

# Run with coverage
pytest tests/ --cov=rapidrmf --cov-report=term-missing -q

# Run specific tests
pytest tests/test_gcp_collectors.py -v

# Lint and format
ruff check rapidrmf tests
black rapidrmf tests
```

4) **Push and Open a PR**
- Push your branch to your fork
- Open a PR against main
- Fill out the PR template and link related issues

---

## Coding Standards

### Python Style
- Formatter: black (100 char line length)
- Linter: ruff (auto-fix preferred)
- Imports: PEP 8 grouping (stdlib → third-party → local)
- Type hints: Required for all public functions
- Docstrings: Required for public classes and methods (Google style)

```python
def collect_evidence(service: str, config: dict[str, object]) -> dict[str, object]:
    """Collect evidence for a service.

    Args:
        service: Service name (e.g., "aws-iam", "gcp-storage")
        config: Collector configuration and credentials

    Returns:
        Evidence payload with metadata and checksum.
    """
    ...
```

### Async/IO Conventions
- Prefer async I/O when available in collectors and network calls
- Avoid blocking calls in async contexts; use asyncio.sleep() instead of time.sleep()

### Logging
- Use rapidrmf.logging_utils.configure_logging() and per-module loggers
- Prefer structured messages with context

### Domain Conventions (RapidRMF)
- Collectors should use finalize_evidence() for consistent metadata/checksums
- Keep collect_* functions small and deterministic
- Validation should surface actionable messages and link to manifests

---

## Testing

### Requirements
- All new features need tests
- All bug fixes need regression tests
- Prefer unit tests for logic; use integration tests for collectors, DB, and CLI paths

### Quick Commands
```bash
# Full suite
pytest tests/ -q

# Integration focus
pytest tests/integration/ -q

# With coverage
pytest tests/ --cov=rapidrmf --cov-report=term-missing -q
```

### Fixtures
- Use provided fixtures to avoid external side effects (mock AWS/GCP clients, temp storage)
- Keep tests hermetic; no live cloud calls in CI

---

## Submitting a Pull Request

### Checklist
- [ ] Tests pass (pytest tests/ -q)
- [ ] Lint/format clean (ruff check, black)
- [ ] Type hints present for public APIs
- [ ] Docstrings added/updated
- [ ] Docs updated if behavior changed
- [ ] Conventional commit messages
- [ ] Related issues linked

### Commit Messages
Follow conventional commits:
- feat(scope): description
- fix(scope): description
- docs(scope): description
- refactor(scope): description
- test(scope): description
- chore(scope): description

Examples:
- feat(collectors): add azure storage lifecycle evidence
- fix(policy): handle missing waiver metadata
- docs(api): update readiness report examples
- test(db): add repository integration coverage

---

## Review Process
- Automated checks must pass (tests, lint, format)
- At least one maintainer approval
- Squash merge preferred for clean history
- Reviewers look for: tests included, style compliance, no breaking changes without discussion, updated docs when needed

---

## Release Process
- Maintainers manage releases
- Version bump in pyproject.toml
- Update CHANGELOG.md
- Tag and create GitHub release
- CI/CD handles packaging and publishing

---

## Getting Help
- Questions: Open a GitHub Discussion
- Bugs: Open an Issue (use the template)
- Feature ideas: Open an Issue or Discussion

---

## Recognition
- Contributors appear in the GitHub contributors list
- Significant contributions are noted in release notes
- Major features may receive special thanks in the README

---

Thank you for contributing to RapidRMF!
