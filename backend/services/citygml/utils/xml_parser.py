"""
XML parsing utilities for CityGML documents.

This module provides helper functions for extracting data from CityGML XML elements,
including text extraction and generic attribute parsing.
"""

from typing import Optional, Dict
import xml.etree.ElementTree as ET

from ..core.constants import NS


def first_text(elem: Optional[ET.Element]) -> Optional[str]:
    """
    Extract and strip text content from an XML element.

    Args:
        elem: XML element or None

    Returns:
        Stripped text content, or None if element is None or has no text

    Examples:
        >>> elem = ET.fromstring('<tag>  Hello  </tag>')
        >>> first_text(elem)
        'Hello'

        >>> first_text(None)
        None

        >>> elem = ET.fromstring('<tag></tag>')
        >>> first_text(elem)
        None
    """
    return (elem.text or "").strip() if elem is not None and elem.text else None


def extract_generic_attributes(building: ET.Element) -> Dict[str, str]:
    """
    Extract generic attributes from a CityGML building element.

    PLATEAU CityGML often stores metadata like building IDs, addresses,
    and other properties in gen:genericAttribute elements. This function
    extracts all string and integer attributes.

    Supported attribute types:
    - gen:stringAttribute
    - gen:intAttribute
    - uro:buildingIDAttribute (PLATEAU-specific)

    Args:
        building: bldg:Building element

    Returns:
        Dictionary mapping attribute names to values (all converted to strings)

    Example:
        >>> # XML structure:
        >>> # <bldg:Building>
        >>> #   <gen:stringAttribute name="address">
        >>> #     <gen:value>Tokyo</gen:value>
        >>> #   </gen:stringAttribute>
        >>> #   <gen:intAttribute name="floors">
        >>> #     <gen:value>10</gen:value>
        >>> #   </gen:intAttribute>
        >>> #   <uro:buildingIDAttribute>
        >>> #     <uro:BuildingIDAttribute>
        >>> #       <uro:buildingID>BLD123</uro:buildingID>
        >>> #     </uro:BuildingIDAttribute>
        >>> #   </uro:buildingIDAttribute>
        >>> # </bldg:Building>
        >>> attrs = extract_generic_attributes(building)
        >>> attrs
        {'address': 'Tokyo', 'floors': '10', 'buildingID': 'BLD123'}
    """
    attributes: Dict[str, str] = {}

    # Find all string generic attribute elements
    for attr in building.findall(".//gen:stringAttribute", NS):
        name_elem = attr.get("name")
        value_elem = attr.find("./gen:value", NS)

        if name_elem and value_elem is not None:
            value = first_text(value_elem)
            if value:
                attributes[name_elem] = value

    # Also check for intAttribute (integer generic attributes)
    for attr in building.findall(".//gen:intAttribute", NS):
        name_elem = attr.get("name")
        value_elem = attr.find("./gen:value", NS)

        if name_elem and value_elem is not None:
            value = first_text(value_elem)
            if value:
                attributes[name_elem] = value

    # Check for PLATEAU-specific uro:buildingIDAttribute
    # Format: <uro:buildingIDAttribute><uro:BuildingIDAttribute><uro:buildingID>value</uro:buildingID>...
    for bid_attr in building.findall(".//uro:buildingIDAttribute/uro:BuildingIDAttribute", NS):
        bid_elem = bid_attr.find("./uro:buildingID", NS)
        if bid_elem is not None:
            bid = first_text(bid_elem)
            if bid:
                attributes["buildingID"] = bid

    return attributes


def get_element_id(elem: ET.Element) -> Optional[str]:
    """
    Get the gml:id attribute from an XML element.

    Args:
        elem: XML element

    Returns:
        gml:id value, or None if not present

    Example:
        >>> elem = ET.fromstring('<bldg:Building gml:id="BLD_123" xmlns:gml="http://www.opengis.net/gml"/>')
        >>> get_element_id(elem)
        'BLD_123'
    """
    return elem.get(f"{{{NS['gml']}}}id")


def find_buildings(root: ET.Element) -> list[ET.Element]:
    """
    Find all Building and BuildingPart elements in a CityGML document.

    Args:
        root: Root element of parsed CityGML document

    Returns:
        List of bldg:Building elements (including BuildingParts)

    Example:
        >>> tree = ET.parse("city.gml")
        >>> root = tree.getroot()
        >>> buildings = find_buildings(root)
        >>> len(buildings)
        150
    """
    return root.findall(".//bldg:Building", NS)
