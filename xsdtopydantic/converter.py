"""Main module containing the converter."""


from types import MappingProxyType
from typing import Any, cast

import pydantic

from xsdtopydantic import api, utils, xsd


def _find_arrays(
    model: type[pydantic.BaseModel], max_depth: int
) -> set[tuple[str, ...]]:
    """Find all the arrays in a pydantic model.

    You may need to limit max_depth to prevent max_recursion.
    """

    def iterate(path: tuple[str, ...], props: dict[str, Any]):
        if len(path) >= max_depth:
            return
        if "anyOf" not in props:
            if props["type"] == "array":
                arrays.add(path)
                if (defintion := props["items"].get("$ref", None)) is None:
                    return
                for child, child_props in definitions[defintion[8:]][
                    "properties"
                ].items():
                    iterate(path + (child,), child_props)

            return
        for type in props["anyOf"]:
            if (defintion := type.get("$ref", None)) is None:
                continue
            for child, child_props in definitions[defintion[8:]]["properties"].items():
                iterate(path + (child,), child_props)

    schema = model.model_json_schema()
    definitions = schema["$defs"]
    arrays: set[tuple[str, ...]] = set()
    for root, props in schema["properties"].items():
        iterate((root,), props)
    return arrays


def convert(path: str, output_path: str | None = None, max_depth: int = 16):
    """Convert an XSD document into a PyDantic schema."""
    data = utils.read_file(path=path)
    if "xsd:schema" not in data:
        raise ValueError("Root node not present, this does not look like an XSD file.")

    root = data["xsd:schema"]
    tmp_data = xsd.XSD(**root)
    xsd_data = {k: v for k, v in root.items() if k.startswith("@")}
    state = tmp_data.compile(api.ConverterState(MappingProxyType(xsd_data)))
    output = ""

    for imp in sorted(
        tuple(state.imports) + ("urllib.request", "typing.*", "xmltodict")
    ):
        if imp == "typing.*" and state.typing_imports:
            output += (
                f"from typing import {', '.join(sorted(list(state.typing_imports)))}\n"
            )
            continue
        output += f"import {imp}\n"
    output += "\n"
    for cls in state.base_type_aliases.keys():
        if (prioritized_type := state.simple_types.pop(cls, None)) is not None:
            output += prioritized_type + "\n"
    for cls in state.simple_types.values():
        output += cls + "\n"
    if state.simple_types:
        output += "\n"
    for cls in state.abstract_classes.values():
        output += cls + "\n"
    if state.abstract_classes:
        output += "\n"
    for cls in state.classes.values():
        output += cls + "\n"

    if state.classes:
        output += "\n"

    output += f'\t"""{state.root_annotation}"""\n'
    output += f"""class Document(pydantic.BaseModel):\n
\t__xsd_data__ = {
            xsd_data
        }
\n"""
    for attr in state.document_attributes.values():
        output += f"\t{attr}\n"
    with utils.module_from_script(output) as module:
        current_schema = cast(type[pydantic.BaseModel], module.Document)
        arrays = _find_arrays(current_schema, max_depth=max_depth)
    output += (
        f"""\t@staticmethod\n\tdef from_xml(path: str)->'Document':
		force_list = {arrays}
		string: str
		if path.startswith("http"):
			string = urllib.request.urlopen(path)
		else:
			with open(path, "r") as fp:
				string = fp.read()
		return Document(**xmltodict.parse(
			string,
			force_list=lambda path, key, _:(tuple(p[0] for p in path) + (key,) in force_list)
		))
	
	def to_xml(
		self, path: str | None = None, namespace_keys: Sequence[str] | None = None
	) -> str:
		namespace_keys = (
			namespace_keys if namespace_keys is not None else tuple(self.__xsd_data__)
		)
		data = self.model_dump(exclude_none=True, by_alias=True)
		root = next(iter(data.keys()))
		data[root] = """
        + """{
			**{k: v for k, v in self.__xsd_data__.items() if k in namespace_keys},
			**data[root],
		}
		output = xmltodict.unparse(data)
		if path is not None:
			with open(path, "w") as fp:
				fp.write(output)
		return output
"""
    )
    if output_path is not None:
        with open(output_path, "w") as fp:
            fp.write(output)
    return output
