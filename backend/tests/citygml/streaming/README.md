# Streaming Parser Tests

Unit tests and benchmarks for CityGML streaming parser implementation (Issue #131).

## Test Structure

```
tests/citygml/streaming/
├── __init__.py
├── test_parser.py              # Core streaming parser tests
├── test_coordinate_optimizer.py # Coordinate parsing tests
├── benchmark_streaming.py       # Performance benchmarks
└── README.md                    # This file
```

## Running Tests

### Prerequisites

```bash
# Install pytest
pip install pytest

# Optional: Install numpy for vectorized coordinate parsing
pip install numpy
```

### Run All Tests

```bash
cd backend
pytest tests/citygml/streaming/ -v
```

### Run Specific Test Files

```bash
# Streaming parser tests
pytest tests/citygml/streaming/test_parser.py -v

# Coordinate optimizer tests
pytest tests/citygml/streaming/test_coordinate_optimizer.py -v
```

### Run Specific Test Functions

```bash
# Run single test
pytest tests/citygml/streaming/test_parser.py::test_stream_parse_single_building -v

# Run tests matching pattern
pytest tests/citygml/streaming/ -k "memory" -v
```

### Run with Coverage

```bash
pytest tests/citygml/streaming/ --cov=services.citygml.streaming --cov-report=html
```

## Running Benchmarks

### Basic Benchmark

```bash
python tests/citygml/streaming/benchmark_streaming.py
```

### With Custom CityGML File

```bash
python tests/citygml/streaming/benchmark_streaming.py --citygml-file path/to/file.gml
```

### Benchmark Options

```bash
# Generate larger sample file (more buildings)
python tests/citygml/streaming/benchmark_streaming.py --num-buildings 1000

# Skip specific benchmarks
python tests/citygml/streaming/benchmark_streaming.py --skip-coordinate
python tests/citygml/streaming/benchmark_streaming.py --skip-memory
python tests/citygml/streaming/benchmark_streaming.py --skip-comparison

# Help
python tests/citygml/streaming/benchmark_streaming.py --help
```

## Test Coverage

### `test_parser.py` (Core Streaming Parser)

**Basic Functionality:**
- ✅ Single building parsing
- ✅ Multiple building parsing
- ✅ Building element verification
- ✅ XLink index construction

**Limit Tests:**
- ✅ Early termination with limit parameter
- ✅ Limit edge cases (0, exceeds total)
- ✅ Correct building count

**Building ID Filtering:**
- ✅ Filter by gml:id attribute
- ✅ Filter by generic attributes (buildingID)
- ✅ No matches handling
- ✅ Multiple ID filtering

**Memory Management:**
- ✅ XLink index isolation per building
- ✅ Memory release verification

**Configuration:**
- ✅ StreamingConfig dataclass
- ✅ Config parameter override

**Error Handling:**
- ✅ Invalid file path
- ✅ Malformed XML
- ✅ Empty files

**Memory Estimation:**
- ✅ Basic memory savings calculation
- ✅ Estimation with limit

### `test_coordinate_optimizer.py` (Coordinate Parsing)

**Optimized Parser (3D):**
- ✅ Basic 3D coordinate parsing
- ✅ Complex 3D coordinates with varying heights
- ✅ Large datasets (1000+ points)

**Optimized Parser (2D):**
- ✅ Basic 2D coordinate parsing
- ✅ Z=None handling

**NumPy Parser (if available):**
- ✅ NumPy 3D coordinate parsing
- ✅ NumPy 2D coordinate parsing
- ✅ Fallback on error

**Edge Cases:**
- ✅ Empty elements
- ✅ Whitespace-only elements
- ✅ Extra whitespace handling
- ✅ Invalid tokens (non-numeric)
- ✅ Invalid dimensionality

**Performance:**
- ✅ Benchmark function
- ✅ NumPy vs optimized speedup
- ✅ Large dataset performance

**Consistency:**
- ✅ Optimized vs NumPy result equivalence

## Benchmark Results

Example output from `benchmark_streaming.py`:

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║              STREAMING PARSER PERFORMANCE BENCHMARK                          ║
║           Issue #131: CityGML XML Streaming Implementation                  ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

================================================================================
BENCHMARK 1: COORDINATE PARSING PERFORMANCE
================================================================================

Dataset: Small (10 points)
----------------------------------------
Optimized (list comprehension): 12.50 μs
NumPy (vectorized):             8.20 μs
Speedup (NumPy vs Optimized):   1.52x

Dataset: Large (1000 points)
----------------------------------------
Optimized (list comprehension): 450.30 μs
NumPy (vectorized):             35.10 μs
Speedup (NumPy vs Optimized):   12.83x

================================================================================
BENCHMARK 2: STREAMING PARSER MEMORY USAGE
================================================================================

Buildings processed: 100
Processing time:     1.25 s
Time per building:   12.50 ms

Current memory:      45.23 MB
Peak memory:         78.50 MB
Memory per building: 785.00 KB

================================================================================
BENCHMARK 3: STREAMING VS LEGACY PARSING
================================================================================

Testing LEGACY method (ET.parse)...
  Buildings found:   50
  Processing time:   2.15 s
  Peak memory:       450.25 MB

Testing STREAMING method (stream_parse_buildings)...
  Buildings found:   50
  Processing time:   0.65 s
  Peak memory:       52.30 MB

================================================================================
COMPARISON RESULTS
================================================================================

Processing Speed:
  Legacy:      2.15 s
  Streaming:   0.65 s
  Speedup:     3.31x faster

Memory Usage:
  Legacy:      450.25 MB
  Streaming:   52.30 MB
  Reduction:   88.4% less memory
```

## Test Data

Tests use dynamically generated CityGML files with:
- Valid XML structure
- Standard CityGML 2.0 namespaces
- LOD2 Building elements with solids
- gml:id attributes for XLink testing
- gen:genericAttribute for filtering tests

## Continuous Integration

To integrate into CI/CD pipeline:

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install pytest numpy
      - name: Run tests
        run: |
          cd backend
          pytest tests/citygml/streaming/ -v
```

## Troubleshooting

### Import Errors

If you get `ModuleNotFoundError`, ensure you're running from the `backend` directory:

```bash
cd backend
pytest tests/citygml/streaming/test_parser.py
```

### NumPy Tests Skipped

If NumPy tests are skipped, install numpy:

```bash
pip install numpy
```

### Memory Profiler Overhead

Memory profiling adds ~10% CPU overhead. For production benchmarks, disable profiling:

```python
config = StreamingConfig(enable_gc_per_building=False)
```

## Contributing

When adding new features to the streaming parser:

1. **Add unit tests** in `test_parser.py` or `test_coordinate_optimizer.py`
2. **Update benchmarks** if performance-critical
3. **Document edge cases** in test docstrings
4. **Run full test suite** before committing

```bash
pytest tests/citygml/streaming/ -v --cov=services.citygml.streaming
```

## References

- **pytest documentation**: https://docs.pytest.org/
- **tracemalloc**: https://docs.python.org/3/library/tracemalloc.html
- **NumPy**: https://numpy.org/doc/stable/
