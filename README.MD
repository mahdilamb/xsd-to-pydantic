# XSD to Pydantic

Python module for converting XSD files to pydantic modules.

**Very early repo - only tested on GPX and TPX schema!**

## Installation

You can either install for development using:

```shell
python -m pip install -e .[test]
```

Add to `pyproject.toml`:

```toml
...
dependencies = [
    "pydantic_stream@git+https://github.com/mahdilamb/xsd-to-pydantic"
]
```

# Usage

```python
from xsdtopydantic import converter

converter.convert(
    "https://www8.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd", "gpx.py"
)

```
