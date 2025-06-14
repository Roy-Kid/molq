# Command Line Examples

This section provides practical examples of using the `@cmdline` decorator for various command-line operations.

## Basic Command Execution

### Simple Commands

```python title="simple_echo.py"
from typing import Generator
from molq import cmdline

@cmdline
def echo_message(message: str) -> str:
    """Echo a message using the system echo command."""
    cp = yield {"cmd": f"echo '{message}'", "block": True}
    return cp.stdout.decode().strip()

if __name__ == "__main__":
    result = echo_message("Hello, Molq!")
    print(result)  # Output: Hello, Molq!
```

### File Operations

```python title="file_operations.py"
from typing import Generator
from molq import cmdline
from pathlib import Path

@cmdline
def list_files(directory: str) -> list:
    """List files in a directory."""
    cp = yield {
        "cmd": ["ls", "-la", directory],
        "block": True
    }
    
    if cp.returncode != 0:
        raise RuntimeError(f"Failed to list directory: {cp.stderr.decode()}")
    
    # Parse the output into a list of files
    lines = cp.stdout.decode().strip().split('\n')[1:]  # Skip total line
    files = []
    for line in lines:
        if line.strip():
            parts = line.split()
            if len(parts) >= 9:
                filename = ' '.join(parts[8:])  # Handle filenames with spaces
                files.append({
                    'permissions': parts[0],
                    'size': parts[4],
                    'name': filename
                })
    return files

@cmdline
def count_lines(filename: str) -> Generator[dict, int, int]:
    """Count lines in a file."""
    cp = yield {
        "cmd": ["wc", "-l", filename],
        "block": True
    }
    
    if cp.returncode != 0:
        raise FileNotFoundError(f"File not found: {filename}")
    
    # Extract line count from output
    output = cp.stdout.decode().strip()
    line_count = int(output.split()[0])
    return line_count

if __name__ == "__main__":
    # List files in current directory
    files = list_files(".")
    print(f"Found {len(files)} files:")
    for file in files[:5]:  # Show first 5 files
        print(f"  {file['name']} ({file['size']} bytes)")
    
    # Count lines in this script
    lines = count_lines(__file__)
    print(f"This script has {lines} lines")
```

### Text Processing

```python title="text_processing.py"
from typing import Generator
from molq import cmdline
import tempfile
import os

@cmdline
def word_count(text: str) -> dict:
    """Count words, lines, and characters in text."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write(text)
        temp_file = f.name
    
    try:
        cp = yield {
            "cmd": ["wc", temp_file],
            "block": True
        }
        
        if cp.returncode != 0:
            raise RuntimeError(f"Word count failed: {cp.stderr.decode()}")
        
        # Parse wc output: lines words characters filename
        output = cp.stdout.decode().strip()
        parts = output.split()
        
        return {
            'lines': int(parts[0]),
            'words': int(parts[1]),
            'characters': int(parts[2])
        }
    finally:
        os.unlink(temp_file)

@cmdline
def grep_search(pattern: str, text: str) -> list:
    """Search for a pattern in text using grep."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write(text)
        temp_file = f.name
    
    try:
        cp = yield {
            "cmd": ["grep", "-n", pattern, temp_file],
            "block": True
        }
        
        # grep returns 1 if no matches found, which is not an error
        if cp.returncode > 1:
            raise RuntimeError(f"Grep failed: {cp.stderr.decode()}")
        
        if cp.returncode == 1:  # No matches
            return []
        
        # Parse grep output: line_number:matched_line
        matches = []
        for line in cp.stdout.decode().strip().split('\n'):
            if ':' in line:
                line_num, content = line.split(':', 1)
                matches.append({
                    'line_number': int(line_num),
                    'content': content
                })
        
        return matches
    finally:
        os.unlink(temp_file)

if __name__ == "__main__":
    sample_text = """
    Hello world!
    This is a sample text.
    World peace is important.
    Programming is fun.
    Hello again!
    """
    
    # Count words
    stats = word_count(sample_text)
    print(f"Text statistics: {stats}")
    
    # Search for pattern
    matches = grep_search("Hello", sample_text)
    print(f"Found 'Hello' in {len(matches)} lines:")
    for match in matches:
        print(f"  Line {match['line_number']}: {match['content'].strip()}")
```

## Data Processing

### CSV Processing

```python title="csv_processing.py"
from typing import Generator
from molq import cmdline
import tempfile
import csv
import os

@cmdline
def csv_stats(csv_data: str) -> dict:
    """Calculate statistics for CSV data using command-line tools."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
        f.write(csv_data)
        temp_file = f.name
    
    try:
        # Count rows (excluding header)
        cp_rows = yield {
            "cmd": ["tail", "-n", "+2", temp_file],  # Skip header
            "block": True
        }
        
        if cp_rows.returncode != 0:
            raise RuntimeError("Failed to process CSV")
        
        row_count = len(cp_rows.stdout.decode().strip().split('\n'))
        if cp_rows.stdout.decode().strip() == '':
            row_count = 0
        
        # Count columns
        cp_cols = yield {
            "cmd": ["head", "-n", "1", temp_file],  # Get header
            "block": True
        }
        
        header = cp_cols.stdout.decode().strip()
        col_count = len(header.split(','))
        
        # Get unique values in first data column (assuming it exists)
        if col_count > 0:
            cp_unique = yield {
                "cmd": f"tail -n +2 {temp_file} | cut -d',' -f1 | sort | uniq | wc -l",
                "block": True
            }
            unique_values = int(cp_unique.stdout.decode().strip()) if cp_unique.returncode == 0 else 0
        else:
            unique_values = 0
        
        return {
            'rows': row_count,
            'columns': col_count,
            'unique_values_first_column': unique_values
        }
    finally:
        os.unlink(temp_file)

@cmdline
def csv_filter(csv_data: str, column_index: int, filter_value: str) -> str:
    """Filter CSV rows based on a column value."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
        f.write(csv_data)
        temp_file = f.name
    
    try:
        # Use awk to filter rows
        awk_command = f"awk -F',' 'NR==1 || ${column_index + 1}==\"{filter_value}\"' {temp_file}"
        
        cp = yield {
            "cmd": awk_command,
            "block": True
        }
        
        if cp.returncode != 0:
            raise RuntimeError(f"CSV filtering failed: {cp.stderr.decode()}")
        
        return cp.stdout.decode()
    finally:
        os.unlink(temp_file)

if __name__ == "__main__":
    # Sample CSV data
    csv_data = """name,age,city
John,25,New York
Jane,30,London
Bob,25,Paris
Alice,35,Tokyo
Charlie,25,Berlin
"""
    
    # Get CSV statistics
    stats = csv_stats(csv_data)
    print(f"CSV Statistics: {stats}")
    
    # Filter by age
    filtered = csv_filter(csv_data, 1, "25")  # Column 1 is age, filter for "25"
    print("People aged 25:")
    print(filtered)
```

### Log Analysis

```python title="log_analysis.py"
from typing import Generator
from molq import cmdline
import tempfile
import os
from datetime import datetime

@cmdline
def analyze_logs(log_content: str) -> dict:
    """Analyze log files for patterns and statistics."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
        f.write(log_content)
        temp_file = f.name
    
    try:
        # Count total lines
        cp_total = yield {
            "cmd": ["wc", "-l", temp_file],
            "block": True
        }
        total_lines = int(cp_total.stdout.decode().split()[0])
        
        # Count error lines
        cp_errors = yield {
            "cmd": ["grep", "-c", "-i", "error", temp_file],
            "block": True
        }
        error_count = int(cp_errors.stdout.decode().strip()) if cp_errors.returncode == 0 else 0
        
        # Count warning lines
        cp_warnings = yield {
            "cmd": ["grep", "-c", "-i", "warning", temp_file],
            "block": True
        }
        warning_count = int(cp_warnings.stdout.decode().strip()) if cp_warnings.returncode == 0 else 0
        
        # Get unique IP addresses (assuming log format with IPs)
        cp_ips = yield {
            "cmd": r"grep -oE '\b([0-9]{1,3}\.){3}[0-9]{1,3}\b' " + temp_file + " | sort | uniq | wc -l",
            "block": True
        }
        unique_ips = int(cp_ips.stdout.decode().strip()) if cp_ips.returncode == 0 else 0
        
        return {
            'total_lines': total_lines,
            'errors': error_count,
            'warnings': warning_count,
            'unique_ips': unique_ips
        }
    finally:
        os.unlink(temp_file)

@cmdline
def extract_errors(log_content: str) -> list:
    """Extract all error lines from logs."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
        f.write(log_content)
        temp_file = f.name
    
    try:
        cp = yield {
            "cmd": ["grep", "-i", "-n", "error", temp_file],
            "block": True
        }
        
        if cp.returncode == 1:  # No matches
            return []
        elif cp.returncode > 1:
            raise RuntimeError(f"Error extraction failed: {cp.stderr.decode()}")
        
        errors = []
        for line in cp.stdout.decode().strip().split('\n'):
            if ':' in line:
                line_num, content = line.split(':', 1)
                errors.append({
                    'line_number': int(line_num),
                    'content': content.strip()
                })
        
        return errors
    finally:
        os.unlink(temp_file)

if __name__ == "__main__":
    # Sample log content
    log_content = """
2024-01-01 10:00:01 INFO  Application started
2024-01-01 10:00:02 INFO  User 192.168.1.100 logged in
2024-01-01 10:01:15 WARNING Database connection slow
2024-01-01 10:02:30 ERROR Failed to connect to database
2024-01-01 10:02:31 INFO  Retrying database connection
2024-01-01 10:02:32 INFO  User 192.168.1.101 logged in
2024-01-01 10:03:45 ERROR Authentication failed for user admin
2024-01-01 10:04:00 WARNING Memory usage high: 85%
2024-01-01 10:05:00 INFO  User 192.168.1.100 logged out
"""
    
    # Analyze logs
    analysis = analyze_logs(log_content)
    print(f"Log Analysis: {analysis}")
    
    # Extract errors
    errors = extract_errors(log_content)
    print(f"\nFound {len(errors)} errors:")
    for error in errors:
        print(f"  Line {error['line_number']}: {error['content']}")
```

## System Administration

### System Monitoring

```python title="system_monitoring.py"
from typing import Generator
from molq import cmdline
import json

@cmdline
def check_disk_usage() -> dict:
    """Check disk usage across all mounted filesystems."""
    cp = yield {
        "cmd": ["df", "-h"],
        "block": True
    }
    
    if cp.returncode != 0:
        raise RuntimeError(f"Failed to check disk usage: {cp.stderr.decode()}")
    
    lines = cp.stdout.decode().strip().split('\n')[1:]  # Skip header
    filesystems = []
    
    for line in lines:
        parts = line.split()
        if len(parts) >= 6:
            filesystems.append({
                'filesystem': parts[0],
                'size': parts[1],
                'used': parts[2],
                'available': parts[3],
                'use_percent': parts[4],
                'mount_point': parts[5]
            })
    
    return {'filesystems': filesystems}

@cmdline
def check_memory_usage() -> dict:
    """Check system memory usage."""
    cp = yield {
        "cmd": ["free", "-h"],
        "block": True
    }
    
    if cp.returncode != 0:
        raise RuntimeError(f"Failed to check memory usage: {cp.stderr.decode()}")
    
    lines = cp.stdout.decode().strip().split('\n')
    mem_line = lines[1].split()  # Memory line
    
    return {
        'total': mem_line[1],
        'used': mem_line[2],
        'free': mem_line[3],
        'available': mem_line[6] if len(mem_line) > 6 else mem_line[3]
    }

@cmdline
def check_running_processes() -> list:
    """Get list of running processes."""
    cp = yield {
        "cmd": ["ps", "aux"],
        "block": True
    }
    
    if cp.returncode != 0:
        raise RuntimeError(f"Failed to list processes: {cp.stderr.decode()}")
    
    lines = cp.stdout.decode().strip().split('\n')[1:]  # Skip header
    processes = []
    
    for line in lines[:10]:  # Limit to first 10 processes
        parts = line.split(None, 10)  # Split on whitespace, max 11 parts
        if len(parts) >= 11:
            processes.append({
                'user': parts[0],
                'pid': parts[1],
                'cpu_percent': parts[2],
                'memory_percent': parts[3],
                'command': parts[10]
            })
    
    return processes

if __name__ == "__main__":
    # Check disk usage
    disk_info = check_disk_usage()
    print("Disk Usage:")
    for fs in disk_info['filesystems']:
        print(f"  {fs['mount_point']}: {fs['used']}/{fs['size']} ({fs['use_percent']} used)")
    
    # Check memory
    memory_info = check_memory_usage()
    print(f"\nMemory Usage: {memory_info['used']}/{memory_info['total']}")
    
    # Check processes
    processes = check_running_processes()
    print(f"\nTop {len(processes)} processes:")
    for proc in processes:
        print(f"  PID {proc['pid']}: {proc['command'][:50]}... ({proc['cpu_percent']}% CPU)")
```

### Backup Operations

```python title="backup_operations.py"
from typing import Generator
from molq import cmdline
import os
from datetime import datetime
from pathlib import Path

@cmdline
def create_backup(source_dir: str, backup_dir: str) -> dict:
    """Create a compressed backup of a directory."""
    # Ensure backup directory exists
    Path(backup_dir).mkdir(parents=True, exist_ok=True)
    
    # Create timestamped backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_{Path(source_dir).name}_{timestamp}.tar.gz"
    backup_path = os.path.join(backup_dir, backup_name)
    
    # Create compressed backup
    cp = yield {
        "cmd": ["tar", "-czf", backup_path, "-C", os.path.dirname(source_dir), os.path.basename(source_dir)],
        "block": True
    }
    
    if cp.returncode != 0:
        raise RuntimeError(f"Backup failed: {cp.stderr.decode()}")
    
    # Get backup file size
    cp_size = yield {
        "cmd": ["ls", "-lh", backup_path],
        "block": True
    }
    
    size_info = cp_size.stdout.decode().split()[4] if cp_size.returncode == 0 else "unknown"
    
    return {
        'backup_file': backup_path,
        'size': size_info,
        'timestamp': timestamp
    }

@cmdline
def verify_backup(backup_file: str) -> dict:
    """Verify the integrity of a backup file."""
    # Check if file exists and is readable
    if not os.path.exists(backup_file):
        raise FileNotFoundError(f"Backup file not found: {backup_file}")
    
    # Test the archive
    cp = yield {
        "cmd": ["tar", "-tzf", backup_file],
        "block": True
    }
    
    if cp.returncode != 0:
        raise RuntimeError(f"Backup verification failed: {cp.stderr.decode()}")
    
    # Count files in archive
    file_count = len(cp.stdout.decode().strip().split('\n'))
    
    # Get file size
    cp_size = yield {
        "cmd": ["ls", "-lh", backup_file],
        "block": True
    }
    
    size_info = cp_size.stdout.decode().split()[4] if cp_size.returncode == 0 else "unknown"
    
    return {
        'status': 'valid',
        'file_count': file_count,
        'size': size_info
    }

@cmdline
def restore_backup(backup_file: str, restore_dir: str) -> dict:
    """Restore files from a backup."""
    # Ensure restore directory exists
    Path(restore_dir).mkdir(parents=True, exist_ok=True)
    
    # Extract backup
    cp = yield {
        "cmd": ["tar", "-xzf", backup_file, "-C", restore_dir],
        "block": True
    }
    
    if cp.returncode != 0:
        raise RuntimeError(f"Restore failed: {cp.stderr.decode()}")
    
    # Count restored files
    cp_count = yield {
        "cmd": ["find", restore_dir, "-type", "f"],
        "block": True
    }
    
    file_count = len(cp_count.stdout.decode().strip().split('\n')) if cp_count.stdout.decode().strip() else 0
    
    return {
        'status': 'completed',
        'restored_files': file_count,
        'restore_location': restore_dir
    }

if __name__ == "__main__":
    import tempfile
    
    # Create a test directory to backup
    with tempfile.TemporaryDirectory() as test_dir:
        # Create some test files
        test_source = os.path.join(test_dir, "source")
        os.makedirs(test_source)
        
        for i in range(3):
            with open(os.path.join(test_source, f"file_{i}.txt"), 'w') as f:
                f.write(f"Test content {i}\n")
        
        backup_dir = os.path.join(test_dir, "backups")
        
        # Create backup
        backup_info = create_backup(test_source, backup_dir)
        print(f"Backup created: {backup_info}")
        
        # Verify backup
        verify_info = verify_backup(backup_info['backup_file'])
        print(f"Backup verification: {verify_info}")
        
        # Restore backup
        restore_dir = os.path.join(test_dir, "restored")
        restore_info = restore_backup(backup_info['backup_file'], restore_dir)
        print(f"Backup restored: {restore_info}")
```

## Best Practices

### Error Handling

```python
from typing import Generator
@cmdline
def robust_command(filename: str) -> str:
    """Example of robust error handling."""
    try:
        cp = yield {
            "cmd": ["cat", filename],
            "block": True
        }
        
        if cp.returncode != 0:
            error_msg = cp.stderr.decode().strip()
            if "No such file" in error_msg:
                raise FileNotFoundError(f"File not found: {filename}")
            else:
                raise RuntimeError(f"Command failed: {error_msg}")
        
        return cp.stdout.decode()
        
    except Exception as e:
        # Log the error and return a default value or re-raise
        print(f"Error in robust_command: {e}")
        raise
```

### Input Validation

```python
from typing import Generator
@cmdline
def validated_command(user_input: str) -> str:
    """Example of input validation."""
    # Validate input to prevent command injection
    if any(char in user_input for char in [';', '&', '|', '`', '$']):
        raise ValueError("Invalid characters in input")
    
    # Use list format to avoid shell interpretation
    cp = yield {
        "cmd": ["echo", user_input],
        "block": True
    }
    
    return cp.stdout.decode().strip()
```

### Resource Management

```python
from typing import Generator
@cmdline
def resource_managed_command():
    """Example of proper resource management."""
    temp_files = []
    
    try:
        # Create temporary files
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
            f.write("temporary data")
            temp_files.append(f.name)
        
        cp = yield {
            "cmd": ["wc", "-l", temp_files[0]],
            "block": True
        }
        
        return cp.stdout.decode().strip()
        
    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                os.unlink(temp_file)
            except OSError:
                pass  # File might already be deleted
```

## Next Steps

- Explore [Local Jobs](local-jobs.md) for job submission examples
- Learn about [SLURM Jobs](slurm-jobs.md) for cluster computing
- Check [Monitoring](monitoring.md) for job monitoring examples
- Review [API Reference](../api/decorators.md) for detailed decorator documentation
