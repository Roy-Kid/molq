# Development Guide

This guide covers development workflows, testing, and contributing to Molq.

## Development Setup

### Prerequisites

- Python 3.9 or higher
- Git
- Optional: Docker (for testing in different environments)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/molcrafts/molq.git
cd molq
```

2. Install in development mode:
```bash
pip install -e ".[dev]"
```

3. Install pre-commit hooks:
```bash
pre-commit install
```

## Project Structure

```
molq/
├── src/molq/                 # Main package source
│   ├── __init__.py          # Package initialization
│   ├── base.py              # Base classes and utilities
│   ├── resources.py         # Resource specification models
│   ├── submit.py            # Main decorator functions
│   ├── cli/                 # Command line interface
│   │   └── main.py         # CLI implementation
│   └── submitor/           # Job submitters
│       ├── __init__.py
│       ├── base.py         # Base submitter class
│       ├── local.py        # Local execution
│       └── slurm.py        # SLURM integration
├── tests/                   # Test suite
│   ├── conftest.py         # Pytest configuration and fixtures
│   ├── test_*.py           # Individual test modules
│   └── integration/        # Integration tests
├── docs/                   # Documentation source
├── example/                # Example scripts
├── scripts/                # Development scripts
│   └── cleanup.sh         # Environment cleanup
└── pyproject.toml         # Project configuration
```

## Testing

### Running Tests

Run the full test suite:
```bash
pytest
```

Run specific test modules:
```bash
pytest tests/test_local.py
pytest tests/test_job_db.py
```

Run with coverage:
```bash
pytest --cov=molq --cov-report=html
```

### Test Organization

- **Unit Tests**: Test individual functions and classes
  - `test_base.py` - Base submitter functionality
  - `test_local.py` - Local submitter
  - `test_resources.py` - Resource specifications
  
- **Integration Tests**: Test complete workflows
  - `test_job_db.py` - Job database operations
  - `test_cli.py` - Command line interface
  
- **End-to-End Tests**: Test real job submission and tracking
  - `test_e2e_local.py` - Local job execution
  - `test_e2e_slurm.py` - SLURM job execution (requires SLURM)

### Test Fixtures

The test suite uses several fixtures defined in `conftest.py`:

#### `tmp_molq_home`
Provides isolated temporary directories for tests:
```python
def test_job_database(tmp_molq_home):
    """Test job database operations in isolation."""
    submitter = LocalSubmitor()
    
    # Job database will be created in tmp_molq_home/.molq/
    job_id = submitter.local_submit(
        job_name='test-job',
        cmd=['echo', 'hello']
    )
    
    jobs = submitter.list_jobs('local')
    assert len(jobs) == 1
    # Cleanup is automatic
```

#### Writing New Tests

When adding new functionality, ensure tests:

1. Use the `tmp_molq_home` fixture for file isolation
2. Test both success and failure cases
3. Clean up any resources they create
4. Are platform-independent where possible

Example test structure:
```python
def test_new_feature(tmp_molq_home):
    """Test new feature with proper isolation."""
    # Setup
    submitter = LocalSubmitor()
    
    # Test
    result = submitter.new_method()
    
    # Assertions
    assert result is not None
    
    # Cleanup is automatic with tmp_molq_home
```

## Code Quality

### Style Guidelines

- Follow PEP 8 for Python code style
- Use type hints for all public functions
- Write docstrings for all public classes and methods
- Keep functions focused and testable

### Linting and Formatting

The project uses several tools for code quality:

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Type checking
mypy src/

# Linting
flake8 src/ tests/
```

### Pre-commit Hooks

Pre-commit hooks automatically run these checks:
```bash
# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## Documentation

### Building Documentation

The documentation is built using MkDocs:

```bash
# Install documentation dependencies
pip install -e ".[docs]"

# Serve documentation locally
mkdocs serve

# Build static documentation
mkdocs build
```

### Documentation Structure

- **Getting Started**: Installation and basic usage
- **User Guide**: Detailed usage instructions
- **Examples**: Practical code examples
- **API Reference**: Generated from docstrings
- **Development**: This guide and contributing information

### Writing Documentation

- Use clear, concise language
- Provide working code examples
- Include both simple and advanced usage patterns
- Link related concepts together

## Database Management

### Job Database Schema

The SQLite job database stores:
```sql
CREATE TABLE jobs (
    section TEXT,      -- Scheduler type (local, slurm)
    job_id INTEGER,    -- Job identifier
    job_name TEXT,     -- Human-readable name
    status TEXT,       -- Job status enum
    command TEXT,      -- Executed command
    work_dir TEXT,     -- Working directory
    submit_time REAL,  -- Submission timestamp
    start_time REAL,   -- Start timestamp
    end_time REAL,     -- Completion timestamp
    extra_info TEXT,   -- JSON metadata
    PRIMARY KEY (section, job_id)
);
```

### Database Testing

Use the `tmp_molq_home` fixture for database isolation:
```python
def test_database_operations(tmp_molq_home):
    """Test database operations with clean state."""
    submitter = BaseSubmitor()
    
    # Database created in temporary location
    submitter.register_job(
        section='test',
        job_id=1,
        job_name='test-job',
        status=JobStatus.Status.RUNNING
    )
    
    jobs = submitter.list_jobs('test')
    assert len(jobs) == 1
```

## CLI Development

### Command Structure

The CLI is built using Click:
```python
@click.command()
@click.option('--scheduler', required=True)
@click.option('--job-name', required=True)
def submit_command(scheduler, job_name):
    """Submit a new job."""
    pass
```

### Testing CLI Commands

Use Click's testing utilities:
```python
from click.testing import CliRunner
from molq.cli.main import cli

def test_cli_submit(tmp_molq_home):
    """Test CLI job submission."""
    runner = CliRunner()
    result = runner.invoke(cli, [
        'submit', 
        '--scheduler', 'local',
        '--cmd', 'echo hello',
        '--job-name', 'test'
    ])
    assert result.exit_code == 0
```

## Submitter Development

### Adding New Submitters

To add support for a new job scheduler:

1. Create a new submitter class inheriting from `BaseSubmitor`
2. Implement required abstract methods
3. Add tests for the new submitter
4. Update documentation

Example submitter structure:
```python
class NewSubmitor(BaseSubmitor):
    """Submit jobs to a new scheduler."""
    
    def local_submit(self, job_name: str, cmd: str | list[str], **kwargs) -> int:
        """Submit job locally."""
        # Implementation
        pass
    
    def remote_submit(self, job_name: str, cmd: str | list[str], **kwargs) -> int:
        """Submit job remotely."""
        # Implementation
        pass
    
    def refresh_job_status(self, job_id: int) -> JobStatus | None:
        """Refresh job status from scheduler."""
        # Implementation
        pass
    
    def cancel(self, job_id: int) -> None:
        """Cancel a running job."""
        # Implementation
        pass
```

### Required Methods

All submitters must implement:
- `refresh_job_status()` - Update job status from scheduler
- `cancel()` - Cancel running jobs
- Job submission methods (`local_submit`, `remote_submit`)

## Release Process

### Version Management

Versions are managed in `pyproject.toml`:
```toml
[project]
version = "0.2.0"
```

### Release Checklist

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Run full test suite
4. Build and test package
5. Create git tag
6. Upload to PyPI

```bash
# Build package
python -m build

# Test upload
python -m twine upload --repository testpypi dist/*

# Production upload
python -m twine upload dist/*
```

## Debugging

### Common Issues

**Job status not updating**: Check scheduler access and permissions
**Database locked**: Ensure no other Molq processes are running
**Tests failing**: Use `tmp_molq_home` fixture for isolation

### Debug Mode

Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Your Molq code here
```

### Environment Cleanup

Use the cleanup script to reset development environment:
```bash
./scripts/cleanup.sh
```

This removes:
- Python cache files (`__pycache__`, `*.pyc`)
- Build artifacts (`build/`, `dist/`, `*.egg-info`)
- Test caches (`.pytest_cache`, `.coverage`)
- Temporary files

## Contributing

### Pull Request Process

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Update documentation
5. Submit pull request

### Contribution Guidelines

- Include tests for new features
- Update documentation as needed
- Follow existing code style
- Write clear commit messages
- Keep pull requests focused

### Issues and Feature Requests

- Use GitHub issues for bug reports
- Provide minimal reproduction cases
- Include system information
- Suggest solutions when possible

## Continuous Integration

The project uses GitHub Actions for:
- Running tests on multiple Python versions
- Code quality checks
- Documentation building
- Automated releases

### CI Configuration

See `.github/workflows/` for CI configuration files.

### Local CI Testing

You can run similar checks locally:
```bash
# Run tests on multiple Python versions
tox

# Check code quality
pre-commit run --all-files

# Build documentation
mkdocs build --strict
```
