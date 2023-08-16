"""Schematics for XSD elements."""
import dataclasses
from types import MappingProxyType
from typing import Literal, Mapping, Sequence

import pydantic

from xsdtopydantic import api, utils

TYPES: Mapping[str, str | tuple[str, ...]] = MappingProxyType(
    {
        "xsd:double": "float",
        "xsd:integer": "int",
        "xsd:float": "float",
        "xsd:decimal": "float",
        "xsd:anyURI": "pydantic.AnyUrl",
        "xsd:token": "str",
        "xsd:positiveInteger": ("int", "annotated_types.Gt(0)"),
        "xsd:unsignedByte": (
            "int",
            f"annotated_types.Ge(0), annotated_types.Lt({2**8})",
        ),
        "xsd:string": "str",
        "xsd:dateTime": "datetime.datetime",
        "xsd:date": "datetime.date",
        "xsd:unsignedShort": (
            "int",
            f"annotated_types.Ge(0), annotated_types.Lt({2**16})",
        ),
        "xsd:unsignedInt": (
            "int",
            f"annotated_types.Ge(0), annotated_types.Lt({2**32})",
        ),
        "xsd:nonNegativeInteger": (
            "int",
            f"annotated_types.Ge(0)",
        ),
        "xsd:boolean": "bool",
        "xsd:gYear": (
            "str",
            r'pydantic.constr(pattern=r"^[-]?\d{4,}(?:Z|[+-]{1}\d{2}[:]?\d{2})?$")',
        ),
    }
)


class XSDAnnotation(api.Convertable):
    """Model for XDS annotation."""

    documentation: str = pydantic.Field(
        alias="xsd:documentation",
    )

    def _convert(self, _):
        return "".join([line.strip() for line in self.documentation.splitlines()])


class XSDAttribute(api.Convertable):
    """Model for XSD attribute."""

    name: str = pydantic.Field(alias="@name")
    type: str = pydantic.Field(alias="@type")
    use: Literal["required"] | None = pydantic.Field(alias="@use", default=None)

    def _convert(self, state: api.ConverterState) -> str:
        alias = utils.snake_case(self.name)
        type, _ = _base_type(self.name, self.type, state)
        # TODO @use
        return f'{alias}: {type} = pydantic.Field(alias="@{self.name}")'


class XSDElement(api.Convertable):
    """Model for XDS element."""

    name: str = pydantic.Field(alias="@name")
    type: str = pydantic.Field(alias="@type")
    min_occurs: int | None = pydantic.Field(alias="@minOccurs", default=None)
    max_occurs: int | None | Literal["unbounded"] = pydantic.Field(
        alias="@maxOccurs", default=None
    )
    annotation: XSDAnnotation | None = pydantic.Field(
        alias="xsd:annotation", default=None
    )

    def _convert(self, state: api.ConverterState) -> str:
        type, _ = _base_type(self.name, self.type, state)
        if type not in state.classes and TYPES.get(self.type, None) is None:
            type = f"'{type}'"
        name = self.name
        alias = utils.snake_case(self.name)
        if alias == name:
            alias = None

        if self.max_occurs == "unbounded":
            type = f"Sequence[{type}]"
            state.typing_imports.add("Sequence")
            # TODO force list
        if not self.min_occurs:
            if self.max_occurs == "unbounded":
                type += f" = pydantic.Field(default_factory=tuple"
            else:
                if type.endswith("'"):
                    state.typing_imports.add("Optional")
                    type = "Optional[" + type + f"] = pydantic.Field(default=None"
                else:
                    type += f" | None = pydantic.Field(default=None"
            if alias:
                type += f', alias="{(name)}"'
                name = alias
                alias = None
            type += ")"

        annotation = _docstring(self.annotation, state, multiline=False)
        if alias:
            alias = f' = pydantic.Field(alias="{(name:=alias)}")'
        return f"{name}: {type}{annotation}{ alias or ''}"


class XSDSequence(api.Convertable):
    """Model for XSD sequence."""

    annotation: XSDAnnotation | None = pydantic.Field(
        alias="xsd:annotation", default=None
    )
    elements: Sequence[XSDElement] = pydantic.Field(
        alias="xsd:element", default_factory=list
    )

    def _convert(self, state: api.ConverterState) -> str:
        output = _docstring(self.annotation, state, True)
        if output:
            output += "\n"
        for element in self.elements:
            output += f"{element._convert(state)}\n"
        return output


class XSDExtension(api.Convertable):
    """Model for XSD extension (derived type)."""

    base: str = pydantic.Field(alias="@base")
    sequence: XSDSequence | None = pydantic.Field(alias="xsd:sequence", default=None)

    def _convert(self, state: api.ConverterState) -> str:
        if self.sequence:
            return self.sequence._convert(state)
        return ""


class XSDComplexContent(api.Convertable):
    """Model for XSD complex content (derived type content)."""

    extension: XSDExtension = pydantic.Field(alias="xsd:extension")

    def _convert(self, state: api.ConverterState) -> str:
        return self.extension._convert(state)


class XSDComplexType(api.Convertable):
    """Model for XSD complex type."""

    annotation: XSDAnnotation | None = pydantic.Field(
        alias="xsd:annotation", default=None
    )
    name: str = pydantic.Field(alias="@name")
    abstract: bool = pydantic.Field(alias="@abstract", default=False)
    sequence: XSDSequence | None = pydantic.Field(alias="xsd:sequence", default=None)
    attributes: Sequence[XSDAttribute] = pydantic.Field(
        alias="xsd:attribute", default_factory=list
    )
    complex_content: XSDComplexContent | None = pydantic.Field(
        alias="xsd:complexContent", default=None
    )

    def _convert(self, state: api.ConverterState) -> str:
        output = f"class {self.name}("
        if self.complex_content:
            output += self.complex_content.extension.base
        else:
            output += "pydantic.BaseModel"
        if self.abstract:
            state.imports.add("abc")
            output += ", abc.ABC"

        output += "):\n"
        if docstring := _docstring(self.annotation, state, True):
            output += f"\t{docstring}\n"
        if self.sequence:
            output += "\t" + ("\n\t".join(self.sequence._convert(state).splitlines()))
        elif self.complex_content:
            output += "\t" + (
                "\n\t".join(self.complex_content._convert(state).splitlines())
            )

        for attribute in self.attributes:
            output += f"\n\t{attribute._convert(state)}"
        if output.rstrip()[-1] == ":":
            output = output.rstrip() + "\n\t...\n"
        return output + "\n"


class XSDRestriction(api.Convertable):
    """Model for XDS restriction - rules for subtypes of native types."""

    annotation: XSDAnnotation | None = pydantic.Field(
        alias="xsd:annotation", default=None
    )
    base: str = pydantic.Field(alias="@base")
    enumeration: tuple[str, ...] | None = pydantic.Field(
        default=None, alias="xsd:enumeration"
    )
    length: int | None = pydantic.Field(alias="xsd:length", default=None)
    min_length: int | None = pydantic.Field(alias="xsd:minLength", default=None)
    max_length: int | None = pydantic.Field(alias="xsd:maxLength", default=None)
    pattern: str | None = pydantic.Field(alias="xsd:pattern", default=None)
    white_space: Literal["collapse"] | None = pydantic.Field(
        alias="xsd:whiteSpace", default=None
    )
    min_inclusive: int | float | None = pydantic.Field(
        alias="xsd:minInclusive", default=None
    )
    max_inclusive: int | float | None = pydantic.Field(
        alias="xsd:maxInclusive", default=None
    )

    @pydantic.field_validator(
        "length",
        "max_inclusive",
        "min_inclusive",
        "min_length",
        "max_length",
        mode="before",
    )
    @classmethod
    def _validate_number(
        cls, v: dict[Literal["@value"], str] | None, info: pydantic.FieldValidationInfo
    ) -> int | float | None:
        if not v:
            return None
        val = float(v["@value"])
        if info.data["base"] in ("xsd:double", "xsd:float", "xsd:decimal"):
            return val

        return int(val)

    @pydantic.field_validator("pattern", "white_space", mode="before")
    @classmethod
    def _validate_str(cls, v: dict[Literal["@value"], str] | None, _) -> str | None:
        if not v:
            return None
        return v["@value"]

    @pydantic.field_validator("enumeration", mode="before")
    @classmethod
    def _validate_literal(
        cls, v: Sequence[dict[Literal["@value"], str]] | None, _
    ) -> tuple[str, ...] | None:
        if not v:
            return None
        return tuple(w["@value"] for w in v)

    def _convert(self, state: api.ConverterState) -> str:
        rules = []
        if (pattern := self.pattern) is not None:
            rules.append(rf"""pydantic.constr(pattern=r"{pattern}")""")
        if (length := self.length) is not None:
            rules.append(f"pydantic.constr(min_length={length}, max_length={length})")
        if (max_length := self.max_length) is not None:
            rules.append(f"pydantic.constr(max_length={max_length})")
        if (min_length := self.min_length) is not None:
            rules.append(f"pydantic.constr(min_length={min_length})")
        if (max_inclusive := self.max_inclusive) is not None:
            state.imports.add("annotated_types")
            rules.append(f"annotated_types.Le({max_inclusive})")
        if (min_inclusive := self.min_inclusive) is not None:
            state.imports.add("annotated_types")
            rules.append(f"annotated_types.Ge({min_inclusive})")
        return ", ".join(rules) if rules else "None"


class XSDSimpleType(api.Convertable):
    """Model for simple types."""

    name: str = pydantic.Field(alias="@name")
    restriction: XSDRestriction = pydantic.Field(alias="xsd:restriction")

    def _convert(self, state: api.ConverterState) -> str:
        base_type = None
        rule = None
        if (literal := self.restriction.enumeration) is not None:
            base_type = f"Literal{list(literal)}"
            state.typing_imports.add("Literal")
        else:
            base_type, rule = _base_type(self.name, self.restriction.base, state)
        type_annotation = self.restriction._convert(state)
        state.typing_imports.add("TypeAlias")
        state.typing_imports.add("Annotated")
        return f"{self.name}: TypeAlias = Annotated[{base_type}, {(rule+' ,' if rule else '')}{type_annotation}]"


class XSD(pydantic.BaseModel):
    """Model for XSD document."""

    xmlns: pydantic.HttpUrl | None = pydantic.Field(alias="@xmlns")
    xmlns_xsd: str | pydantic.HttpUrl = pydantic.Field(alias="@xmlns:xsd")
    target_namespace: str | pydantic.HttpUrl = pydantic.Field(alias="@targetNamespace")
    element_form_default: Literal["qualified", "unqualified"] | None = pydantic.Field(
        alias="@elementFormDefault", default=None
    )
    annotation: XSDAnnotation | None = pydantic.Field(
        alias="xsd:annotation", default=None
    )
    elements: Sequence[XSDElement] = pydantic.Field(
        alias="xsd:element", default_factory=list
    )
    complex_types: Sequence[XSDComplexType] = pydantic.Field(
        alias="xsd:complexType", default_factory=list
    )
    simple_types: Sequence[XSDSimpleType] = pydantic.Field(
        alias="xsd:simpleType", default_factory=list
    )

    def compile(self, state: api.ConverterState) -> api.ConverterState:
        """Compile the XSD into a state object by traversing it's nodes."""
        state.root_annotation = (
            "" if self.annotation is None else self.annotation._convert(state)
        )

        state._in_complex = True
        for type in self.complex_types:
            (state.abstract_classes if type.abstract else state.classes)[
                type.name
            ] = type._convert(state)
        state._in_complex = False
        for element in self.elements:
            state.document_attributes[element.name] = element._convert(state)
        for simple_type in self.simple_types:
            state.simple_types[simple_type.name] = simple_type._convert(state)
        return state


def _base_type(name: str, type: str, state: api.ConverterState):
    """Find the basetype, updating the state with new aliases."""
    base_type = TYPES.get(type, dataclasses.MISSING)
    rule = None
    if base_type is dataclasses.MISSING:
        base_type = type
    else:
        if isinstance(base_type, tuple):
            base_type, rule = base_type
            if state._in_complex and type.startswith("xsd:"):
                new_type: str
                state.simple_types[new_type] = (
                    XSDSimpleType.model_validate(
                        {
                            "@name": (new_type := type[4:]),
                            "xsd:restriction": XSDRestriction.model_validate(
                                {"@base": base_type}
                            ),
                        }
                    )._convert(state)[:-5]
                    + (rule or "None")
                    + "]"
                )
                base_type = new_type
        state.base_type_aliases[name] = base_type
    if base_type.startswith("datetime."):
        state.imports.add("datetime")
    return base_type, rule


def _docstring(
    annotation: XSDAnnotation | None,
    state: api.ConverterState,
    multiline: bool | None = False,
):
    """Format the annotation into a docstring."""
    if not annotation:
        return ""
    output = f"{annotation._convert(state)}"
    if multiline:
        return f'"""{output}"""'
    elif multiline is None:
        return output
    return f"  # {output}"
