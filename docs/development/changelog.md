# Changelog

All notable changes to Molq will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive documentation with MkDocs Material
- Examples for command-line operations, local jobs, SLURM jobs, and monitoring
- API reference documentation for core functions, submitters, and decorators
- User guide covering decorators, local execution, SLURM integration, and configuration
- Development documentation for contributing, testing, and changelog

### Changed
- Improved documentation structure and navigation
- Enhanced code examples with real-world use cases

### Fixed
- Documentation build configuration
- MkDocs navigation structure

## [0.1.0] - Initial Release

### Added
- Core `@cmdline` decorator for executing shell commands
- `@submit` decorator factory for job submission
- `LocalSubmitor` for running jobs on local machine
- `SlurmSubmitor` for submitting jobs to SLURM clusters
- Base classes for creating custom submitters
- Generator-based configuration interface
- Support for blocking and non-blocking job execution
- Job monitoring and status checking
- Environment variable support
- Working directory specification
- Log file redirection

### Features
- **Command Line Interface**: Execute shell commands with full control
- **Local Execution**: Run jobs on local machine with process management
- **SLURM Integration**: Submit jobs to SLURM-managed clusters via SSH
- **Flexible Configuration**: JSON-like configuration dictionaries
- **Type Safety**: Full type hint support with preserved function signatures
- **Error Handling**: Comprehensive error handling and reporting
- **Job Monitoring**: Check job status and retrieve results
- **Resource Management**: Memory and CPU resource specification

### Submitters
- `LocalSubmitor`: Local process execution
- `SlurmSubmitor`: SLURM cluster job submission
- `BaseSubmitor`: Base class for custom implementations

### Decorators
- `@cmdline`: Direct command execution
- `@submit`: Job submission with registered submitters

### Configuration Options
- `cmd`: Command to execute (string or list)
- `cwd`: Working directory
- `block`: Blocking vs non-blocking execution
- `job_name`: Human-readable job identifier
- `log_file`: Output redirection
- `env`: Environment variables
- SLURM-specific options: partition, time, nodes, memory, etc.

### Development
- Full test suite with pytest
- Type checking with mypy
- Code formatting with black
- Import sorting with isort
- Linting with flake8
- Pre-commit hooks for code quality
- Continuous integration setup

### Documentation
- Installation and quick start guides
- Comprehensive user documentation
- API reference with examples
- Real-world usage patterns
- Best practices and troubleshooting

---

## Version History Format

### [X.Y.Z] - YYYY-MM-DD

#### Added
- New features and functionality

#### Changed
- Changes to existing functionality

#### Deprecated
- Features that will be removed in future versions

#### Removed
- Features that have been removed

#### Fixed
- Bug fixes

#### Security
- Security-related changes

---

## Migration Guides

### Upgrading from 0.x to 1.x (Future)

When version 1.0 is released, migration information will be provided here.

#### Breaking Changes
- Details about breaking changes

#### Migration Steps
- Step-by-step migration instructions

#### Compatibility
- Information about backward compatibility

---

## Release Process

Molq follows semantic versioning:

- **MAJOR** version increments for incompatible API changes
- **MINOR** version increments for backward-compatible functionality additions
- **PATCH** version increments for backward-compatible bug fixes

### Release Checklist

1. Update version in `pyproject.toml`
2. Update this CHANGELOG.md
3. Run full test suite
4. Update documentation
5. Create GitHub release
6. Publish to PyPI

### Pre-release Versions

Pre-release versions use the following suffixes:
- `alpha` (a): Early development version
- `beta` (b): Feature-complete but potentially unstable
- `rc` (release candidate): Final testing before release

Example: `1.0.0a1`, `1.0.0b2`, `1.0.0rc1`

---

## Contributors

### Core Team
- **Roy Kid** - Project creator and maintainer

### Contributors
- Community contributors will be listed here as the project grows

---

## Acknowledgments

- **Hamilton** team for creating the dataflow framework that inspired Molq
- **SLURM** developers for the excellent job scheduler
- **Python** community for the amazing ecosystem of tools and libraries
- All beta testers and early adopters

---

## Support

For questions, bug reports, or feature requests:

- **GitHub Issues**: [molcrafts/molq/issues](https://github.com/molcrafts/molq/issues)
- **Documentation**: [molcrafts.github.io/molq](https://molcrafts.github.io/molq)
- **PyPI Package**: [pypi.org/project/molq](https://pypi.org/project/molq/)

---

*This changelog is automatically updated with each release. For the most recent changes, see the [Unreleased] section at the top.*
