"""Abstract classes for convertable elements."""
import abc
import dataclasses
from typing import Mapping

import pydantic


@dataclasses.dataclass
class ConverterState:
    """The current state of the compiler."""

    xsd_data: Mapping[str, str]
    root_annotation: str | None = None
    document_attributes: dict[str, str] = dataclasses.field(default_factory=dict)

    base_type_aliases: dict[str, str] = dataclasses.field(default_factory=dict)
    simple_types: dict[str, str] = dataclasses.field(default_factory=dict)

    typing_imports: set[str] = dataclasses.field(default_factory=set)
    imports: set[str] = dataclasses.field(default_factory=lambda: {"pydantic"})

    abstract_classes: dict[str, str] = dataclasses.field(default_factory=dict)
    classes: dict[str, str] = dataclasses.field(default_factory=dict)

    _in_complex: bool = False


class Convertable(abc.ABC, pydantic.BaseModel):
    """Interface for a compilable BaseModel."""

    @abc.abstractmethod
    def _convert(self, state: ConverterState) -> str:
        """Convert this element in to the representation required for pydantic."""
