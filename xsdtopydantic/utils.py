"""Utility functions for the converter."""
import contextlib
import importlib
import importlib.util
import random
import re
import sys
import tempfile
import typing
import urllib.request

import xmltodict

SNAKE_CASE_PATTERN = re.compile(r"(?<!^)(?=[A-Z])")


def snake_case(camel_case: str):
    """Convert camelCase to snake_case."""
    return SNAKE_CASE_PATTERN.sub("_", camel_case).lower()


@typing.no_type_check
@contextlib.contextmanager
def module_from_script(script: str):
    """Import a module, given a script to execute."""
    module_name = f"tmp_{random.getrandbits(128):032x}"
    while module_name in sys.modules:
        module_name = f"tmp_{random.getrandbits(128):032x}"
    with tempfile.NamedTemporaryFile("r", suffix=".py") as tmp_file:
        file_path = tmp_file.name
        with open(file_path, "w") as fp:
            fp.write(script)
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        try:
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            yield __import__(module_name)
        finally:
            del sys.modules[module_name]


def read_file(path: str):
    """Read a file."""
    string: str
    if path.startswith("http"):
        string = urllib.request.urlopen(path)  # nosec B310
    else:
        with open(path, "r") as fp:
            string = fp.read()
    return xmltodict.parse(
        string,
        force_list=(
            "xsd:element",
            "xsd:attribute",
            "xsd:enumeration",
        ),
    )
