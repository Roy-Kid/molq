# Testing

This document describes the testing strategy and guidelines for Molq development.

## Test Organization

Molq's test suite is organized to provide comprehensive coverage of all functionality:

```
tests/
├── conftest.py              # Shared pytest fixtures
├── test_base.py             # Core functionality tests
├── test_adaptor.py          # Adapter pattern tests
├── test_cmdline.py          # @cmdline decorator tests
├── test_local.py            # Local submitter tests
├── test_log.py              # Logging functionality tests
├── test_monitor.py          # Job monitoring tests
└── test_usage.py            # Integration and usage tests
```

## Running Tests

### Basic Test Execution

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_local.py

# Run specific test function
pytest tests/test_local.py::test_local_submit_simple_command
```

### Test Coverage

```bash
# Run tests with coverage reporting
pytest --cov=molq

# Generate HTML coverage report
pytest --cov=molq --cov-report=html

# Open coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Parallel Test Execution

```bash
# Install pytest-xdist for parallel execution
pip install pytest-xdist

# Run tests in parallel
pytest -n auto
```

## Test Categories

### Unit Tests

Test individual components in isolation:

```python
def test_base_submitor_initialization():
    """Test BaseSubmitor initializes correctly."""
    config = {"test": "value"}
    submitor = BaseSubmitor(config)
    assert submitor.config == config

def test_cmdline_decorator_basic_functionality():
    """Test @cmdline decorator executes simple commands."""
    @cmdline
    def simple_echo():
        cp = yield {"cmd": "echo hello", "block": True}
        return cp.stdout.decode().strip()
    
    result = simple_echo()
    assert result == "hello"
```

### Integration Tests

Test interactions between components:

```python
def test_local_submitter_with_cmdline():
    """Test local submitter integration with cmdline decorator."""
    local = submit("test_local", "local")
    
    @local
    def test_job():
        job_id = yield {
            "cmd": ["echo", "integration test"],
            "block": True
        }
        return job_id
    
    result = test_job()
    assert isinstance(result, int)
```

### End-to-End Tests

Test complete workflows:

```python
def test_complete_workflow():
    """Test a complete job submission and monitoring workflow."""
    local = submit("e2e_test", "local")
    
    @local
    def data_processing():
        # Submit job
        job_id = yield {
            "job_name": "e2e_test_job",
            "cmd": ["python", "-c", "print('E2E test complete')"],
            "block": False
        }
        return job_id
    
    # Execute and monitor
    job_id = data_processing()
    status = local.get_job_status(job_id)
    assert status in ["RUNNING", "COMPLETED"]
```

## Test Fixtures

### Common Fixtures (conftest.py)

```python
import pytest
import tempfile
from pathlib import Path

@pytest.fixture
def temp_dir():
    """Provide a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def sample_config():
    """Provide a sample configuration dictionary."""
    return {
        "job_name": "test_job",
        "cmd": ["echo", "test"],
        "block": True
    }

@pytest.fixture
def mock_submitter():
    """Provide a mock submitter for testing."""
    from unittest.mock import Mock
    submitter = Mock()
    submitter.submit_job.return_value = 12345
    submitter.get_job_status.return_value = "COMPLETED"
    return submitter
```

### Specific Test Fixtures

```python
@pytest.fixture
def local_submitter():
    """Create a local submitter for testing."""
    return submit("test_local", "local")

@pytest.fixture
def sample_script(temp_dir):
    """Create a sample Python script for testing."""
    script_path = temp_dir / "test_script.py"
    script_path.write_text('''
import sys
print("Hello from test script")
print(f"Args: {sys.argv[1:]}")
''')
    return script_path
```

## Mocking and Patching

### Mocking External Dependencies

```python
from unittest.mock import patch, Mock
import subprocess

@patch('subprocess.run')
def test_cmdline_with_mock(mock_run):
    """Test cmdline decorator with mocked subprocess."""
    # Setup mock
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = b"mocked output"
    mock_result.stderr = b""
    mock_run.return_value = mock_result
    
    @cmdline
    def test_command():
        cp = yield {"cmd": "echo test", "block": True}
        return cp.stdout.decode().strip()
    
    result = test_command()
    assert result == "mocked output"
    mock_run.assert_called_once()
```

### Mocking SLURM Commands

```python
@patch('paramiko.SSHClient')
def test_slurm_submission(mock_ssh_client):
    """Test SLURM job submission with mocked SSH."""
    # Setup SSH mock
    mock_client = Mock()
    mock_ssh_client.return_value = mock_client
    
    # Mock command execution
    mock_stdin = Mock()
    mock_stdout = Mock()
    mock_stderr = Mock()
    mock_stdout.read.return_value = b"Submitted batch job 12345\n"
    mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
    
    # Test SLURM submitter
    slurm = submit("test_slurm", "slurm", {
        "host": "test.cluster.com",
        "username": "testuser"
    })
    
    @slurm
    def test_job():
        job_id = yield {
            "cmd": ["echo", "test"],
            "partition": "compute",
            "block": False
        }
        return job_id
    
    job_id = test_job()
    assert job_id == 12345
```

## Parameterized Tests

Use parametrized tests for testing multiple scenarios:

```python
@pytest.mark.parametrize("command,expected", [
    (["echo", "hello"], "hello"),
    (["python", "-c", "print('test')"], "test"),
    (["ls", "/"], True),  # Just check if command runs
])
def test_cmdline_various_commands(command, expected):
    """Test cmdline decorator with various commands."""
    @cmdline
    def test_cmd():
        cp = yield {"cmd": command, "block": True}
        return cp.stdout.decode().strip()
    
    result = test_cmd()
    if isinstance(expected, str):
        assert result == expected
    elif isinstance(expected, bool):
        assert bool(result) == expected
```

## Error Testing

Test error conditions and edge cases:

```python
def test_cmdline_command_failure():
    """Test cmdline decorator handles command failures."""
    @cmdline
    def failing_command():
        cp = yield {"cmd": ["false"], "block": True}  # Command that returns 1
        return cp.returncode
    
    result = failing_command()
    assert result == 1

def test_invalid_configuration():
    """Test handling of invalid job configurations."""
    local = submit("test_invalid", "local")
    
    @local
    def invalid_job():
        with pytest.raises(ValueError):
            job_id = yield {
                # Missing required 'cmd' parameter
                "job_name": "invalid"
            }
    
    invalid_job()
```

## Performance Testing

Test performance-critical operations:

```python
import time
import pytest

def test_local_submission_performance():
    """Test that local job submission is reasonably fast."""
    local = submit("perf_test", "local")
    
    @local
    def quick_job():
        start_time = time.time()
        job_id = yield {
            "cmd": ["echo", "performance test"],
            "block": True
        }
        end_time = time.time()
        return end_time - start_time
    
    execution_time = quick_job()
    assert execution_time < 1.0  # Should complete within 1 second

@pytest.mark.performance
def test_concurrent_job_submission():
    """Test submitting multiple jobs concurrently."""
    import concurrent.futures
    
    local = submit("concurrent_test", "local")
    
    def submit_job(job_num):
        @local
        def job():
            job_id = yield {
                "cmd": ["echo", f"job_{job_num}"],
                "block": True
            }
            return job_id
        return job()
    
    # Submit 10 jobs concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(submit_job, i) for i in range(10)]
        results = [future.result() for future in futures]
    
    assert len(results) == 10
    assert all(isinstance(result, int) for result in results)
```

## Test Configuration

### pytest.ini

```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
python_classes = Test*
addopts = 
    --strict-markers
    --disable-warnings
    --tb=short
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    performance: marks tests as performance tests
    cluster: marks tests that require cluster access
```

### Test Environment Variables

Set up test-specific environment variables:

```python
import os
import pytest

@pytest.fixture(autouse=True)
def test_environment():
    """Set up test environment variables."""
    old_env = os.environ.copy()
    
    # Set test environment
    os.environ.update({
        'MOLQ_TEST_MODE': '1',
        'MOLQ_LOG_LEVEL': 'DEBUG',
        'TMPDIR': '/tmp'
    })
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(old_env)
```

## Continuous Integration

### GitHub Actions Configuration

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, '3.10', 3.11, 3.12]
    
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e .[dev]
    
    - name: Run tests
      run: |
        pytest --cov=molq --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

## Test Data and Fixtures

### Managing Test Data

```python
import pytest
from pathlib import Path

@pytest.fixture
def test_data_dir():
    """Provide path to test data directory."""
    return Path(__file__).parent / "data"

@pytest.fixture
def sample_csv_file(test_data_dir):
    """Provide a sample CSV file for testing."""
    csv_path = test_data_dir / "sample.csv"
    if not csv_path.exists():
        csv_path.parent.mkdir(exist_ok=True)
        csv_path.write_text("name,age,city\nJohn,25,NYC\nJane,30,LA\n")
    return csv_path
```

## Best Practices

### 1. Write Clear Test Names

```python
# Good
def test_local_submitter_executes_echo_command_successfully():
    pass

# Bad
def test_local():
    pass
```

### 2. Test One Thing at a Time

```python
# Good
def test_job_submission_returns_job_id():
    # Test only job ID return
    pass

def test_job_submission_executes_command():
    # Test only command execution
    pass

# Bad
def test_job_submission():
    # Tests multiple aspects in one test
    pass
```

### 3. Use Descriptive Assertions

```python
# Good
assert result.returncode == 0, f"Command failed with code {result.returncode}"
assert "expected output" in result.stdout.decode()

# Bad
assert result
assert result.returncode == 0
```

### 4. Clean Up Resources

```python
@pytest.fixture
def temp_file():
    """Create a temporary file."""
    fd, path = tempfile.mkstemp()
    try:
        yield path
    finally:
        os.close(fd)
        os.unlink(path)
```

### 5. Mock External Dependencies

```python
# Mock file system operations, network calls, subprocess execution
@patch('subprocess.run')
@patch('os.path.exists')
def test_with_mocked_dependencies(mock_exists, mock_run):
    # Test logic without external dependencies
    pass
```

## Running Tests in Different Environments

### Local Development

```bash
# Quick test run during development
pytest tests/test_local.py -v

# Run with coverage
pytest --cov=molq tests/

# Run only fast tests
pytest -m "not slow"
```

### CI/CD Pipeline

```bash
# Full test suite with coverage
pytest --cov=molq --cov-report=xml --cov-report=html

# Integration tests
pytest -m integration

# Performance tests
pytest -m performance --tb=short
```

### Docker Testing

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . .

RUN pip install -e .[dev]
CMD ["pytest", "--cov=molq"]
```

```bash
# Build and run tests in Docker
docker build -t molq-tests .
docker run --rm molq-tests
```

## Troubleshooting Tests

### Common Issues

1. **Tests fail in CI but pass locally**
   - Check environment differences
   - Verify test isolation
   - Check for race conditions

2. **Slow test execution**
   - Profile with `pytest --durations=10`
   - Mock expensive operations
   - Use parallel execution

3. **Flaky tests**
   - Add proper waits/timeouts
   - Improve test isolation
   - Use deterministic test data

### Debugging Test Failures

```python
# Add debugging output
def test_with_debug():
    result = some_function()
    print(f"Debug: result={result}")  # Will show in pytest -s
    assert result.is_valid()

# Use pytest debugging
pytest --pdb  # Drop into debugger on failure
pytest --pdb-trace  # Drop into debugger at start of each test
```

## Next Steps

- Review [Contributing Guidelines](contributing.md) for development setup
- Check [Changelog](changelog.md) for testing-related updates
- See [API Reference](../api/core.md) for implementation details
