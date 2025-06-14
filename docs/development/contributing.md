# Contributing to Molq

Thank you for considering contributing to Molq! This guide will help you get started with contributing to the project.

## Development Setup

### Prerequisites

- Python 3.8 or higher
- Git
- A GitHub account

### Setting Up the Development Environment

1. **Fork the repository** on GitHub

2. **Clone your fork**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/molq.git
   cd molq
   ```

3. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. **Install development dependencies**:
   ```bash
   pip install -e .[dev]
   ```

5. **Install pre-commit hooks**:
   ```bash
   pre-commit install
   ```

## Development Workflow

### Creating a Branch

Always create a new branch for your work:

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

### Making Changes

1. **Write tests first** (TDD approach recommended)
2. **Implement your changes**
3. **Run tests** to ensure everything works
4. **Update documentation** if needed

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=molq --cov-report=html

# Run specific test file
pytest tests/test_specific.py

# Run tests with verbose output
pytest -v
```

### Code Style

We use several tools to maintain code quality:

- **Black** for code formatting
- **isort** for import sorting
- **flake8** for linting
- **mypy** for type checking

Run all checks:

```bash
# Format code
black molq tests
isort molq tests

# Lint code
flake8 molq tests

# Type checking
mypy molq
```

### Documentation

Documentation is built with MkDocs Material:

```bash
# Install documentation dependencies
pip install mkdocs mkdocs-material mkdocs-mermaid2-plugin

# Serve documentation locally
mkdocs serve

# Build documentation
mkdocs build
```

## Types of Contributions

### Bug Reports

When filing a bug report, please include:

- **Python version** and operating system
- **Molq version**
- **Steps to reproduce** the bug
- **Expected behavior**
- **Actual behavior**
- **Code samples** that demonstrate the issue

### Feature Requests

When requesting a feature:

- **Describe the problem** your feature would solve
- **Provide use cases** for the feature
- **Consider alternatives** and explain why your approach is best
- **Offer to implement** the feature if possible

### Code Contributions

#### Adding New Submitters

To add support for a new job submission system:

1. **Create a new submitter class** in `src/molq/submitor/`
2. **Inherit from `BaseSubmitor`**
3. **Implement required methods**:
   - `submit_job(config: dict) -> int`
   - `get_job_status(job_id: int) -> str`
   - `cancel_job(job_id: int) -> bool`

Example:

```python
from typing import Generator
from molq.submitor.base import BaseSubmitor

class MySubmitor(BaseSubmitor):
    def __init__(self, config: dict):
        super().__init__(config)
        # Initialize your submitter
    
    def submit_job(self, config: dict) -> Generator[dict, int, int]:
        # Submit job and return job ID
        pass
    
    def get_job_status(self, job_id: int) -> str:
        # Return job status
        pass
    
    def cancel_job(self, job_id: int) -> bool:
        # Cancel job and return success status
        pass
```

4. **Add tests** for your submitter
5. **Update documentation** with usage examples

#### Improving Existing Features

- **Write tests** for your improvements
- **Maintain backward compatibility**
- **Update documentation** for any API changes
- **Follow existing code patterns**

## Testing Guidelines

### Test Structure

Tests are organized in the `tests/` directory:

```
tests/
├── conftest.py          # Shared test fixtures
├── test_base.py         # Core functionality tests
├── test_local.py        # Local submitter tests
├── test_cmdline.py      # Cmdline decorator tests
└── ...
```

### Writing Tests

1. **Use descriptive test names**:
   ```python
from typing import Generator
   def test_local_submitter_executes_simple_command():
       pass
   ```

2. **Use fixtures for setup**:
   ```python
from typing import Generator
   @pytest.fixture
   def temp_dir():
       with tempfile.TemporaryDirectory() as tmpdir:
           yield tmpdir
   ```

3. **Test both success and failure cases**:
   ```python
from typing import Generator
   def test_command_success():
       # Test successful execution
       pass
   
   def test_command_failure():
       # Test error handling
       pass
   ```

4. **Mock external dependencies**:
   ```python
from typing import Generator
   @patch('subprocess.run')
   def test_command_execution(mock_run):
       # Test without actual subprocess execution
       pass
   ```

### Test Coverage

Aim for high test coverage, especially for:

- **Core functionality**
- **Error handling**
- **Edge cases**
- **Public APIs**

## Pull Request Process

### Before Submitting

1. **Ensure all tests pass**
2. **Check code style** with linting tools
3. **Update documentation** if needed
4. **Add changelog entry** if appropriate

### Submitting the PR

1. **Push your branch** to your fork
2. **Create a pull request** on GitHub
3. **Fill out the PR template** completely
4. **Link to relevant issues**

### PR Review Process

1. **Automated checks** will run (tests, linting, etc.)
2. **Maintainers will review** your code
3. **Address feedback** by updating your branch
4. **PR will be merged** once approved

## Code Review Guidelines

### For Reviewers

- **Be constructive** and helpful
- **Ask questions** if something is unclear
- **Suggest improvements** rather than just pointing out problems
- **Acknowledge good work**

### For Contributors

- **Respond to feedback** promptly
- **Ask for clarification** if needed
- **Don't take criticism personally**
- **Thank reviewers** for their time

## Release Process

Releases follow semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

## Getting Help

If you need help with development:

- **Check existing issues** and documentation
- **Ask questions** in issue discussions
- **Join the community** (if applicable)
- **Reach out to maintainers**

## Recognition

Contributors are recognized in:

- **CHANGELOG.md** for their contributions
- **AUTHORS.md** file (if created)
- **Release notes** for significant contributions

Thank you for contributing to Molq! 🚀
