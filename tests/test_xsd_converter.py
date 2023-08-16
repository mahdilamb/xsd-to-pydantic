from xsdtopydantic import converter, utils


def tcx_test():
    """Test that we can read TCX file from the converted model."""
    with utils.module_from_script(
        converter.convert(
            "https://www8.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd"
        )
    ) as module:
        module.Document.from_xml("https://api.runnermaps.nl/route_575.tcx")


def gpx_test():
    """Test that we can read GPX file from the converted model."""
    with utils.module_from_script(
        converter.convert("https://www.topografix.com/gpx/1/1/gpx.xsd")
    ) as module:
        module.Document.from_xml("https://www.topografix.com/fells_loop.gpx")


if __name__ == "__main__":
    import sys

    import pytest

    sys.exit(pytest.main(["-v", "-s"] + sys.argv))
