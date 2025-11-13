# Testing Guide

## Running Tests

### Run all tests
```bash
pytest
```

### Run specific test file
```bash
pytest tests/test_validate.py
pytest tests/test_exchanges/test_coinbase.py
```

### Run specific test class or function
```bash
pytest tests/test_validate.py::TestValidatePayload
pytest tests/test_validate.py::TestValidatePayload::test_valid_payload
```

### Run with coverage
```bash
pytest --cov=. --cov-report=html
# Open htmlcov/index.html to view coverage report
```

### Run with verbose output
```bash
pytest -v
pytest -vv  # extra verbose
```

### Run tests matching a pattern
```bash
pytest -k "test_valid"  # runs all tests with "valid" in name
pytest -k "coinbase"    # runs all coinbase-related tests
```

## Test Structure

```
tests/
├── __init__.py                    # Test package marker
├── test_validate.py               # Tests for validate.py
├── test_exchanges/
│   ├── __init__.py
│   └── test_coinbase.py          # Tests for exchanges/coinbase.py
└── conftest.py (optional)         # Shared fixtures
```

## Test Categories

Tests are organized by module:
- `test_validate.py` - Webhook validation tests
- `test_exchanges/test_coinbase.py` - Coinbase authentication tests
- (Future) `test_function_app.py` - Azure Function handler tests

## Writing Tests

### Test naming convention
- Test files: `test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`

### Example test structure
```python
import pytest
from unittest.mock import patch

class TestMyClass:
    """Test MyClass functionality."""
    
    @pytest.fixture
    def sample_data(self):
        """Fixture providing sample test data."""
        return {"key": "value"}
    
    def test_basic_functionality(self, sample_data):
        """Test basic use case."""
        # Arrange
        expected = "result"
        
        # Act
        actual = my_function(sample_data)
        
        # Assert
        assert actual == expected
    
    def test_error_handling(self):
        """Test error conditions."""
        with pytest.raises(ValueError):
            my_function(None)
```

## Coverage Goals

Aim for:
- **80%+** overall coverage
- **100%** for critical paths (authentication, validation)
- **60%+** for integration code

## CI/CD Integration

Tests can be run in CI/CD pipelines:
```yaml
- name: Run tests
  run: |
    pip install -r requirements.txt
    pytest --cov=. --cov-report=xml
```
