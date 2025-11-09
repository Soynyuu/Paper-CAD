"""
XLink reference resolution for CityGML documents.

This module provides functions to build an ID index and resolve XLink references
(xlink:href="#id") in CityGML XML documents. XLink resolution is critical for
accessing shared geometry definitions.

⚠️ CRITICAL: build_id_index() MUST be called before any geometry extraction
(PHASE:1 in the conversion pipeline). All geometry extraction functions depend
on the ID index for XLink resolution.
"""

from typing import Optional, Dict
import xml.etree.ElementTree as ET

from ..core.constants import NS
from .logging import log


def build_id_index(root: ET.Element) -> Dict[str, ET.Element]:
    """
    Build an index of all gml:id attributes in the document.

    This enables efficient resolution of XLink references (xlink:href="#id").
    The index maps gml:id values to their corresponding XML elements.

    ⚠️ CRITICAL: This function MUST be called in PHASE:1, immediately after
    parsing the CityGML document and BEFORE any geometry extraction begins.
    All XLink references will fail silently if the index is not built first.

    Args:
        root: Root element of the parsed GML document

    Returns:
        Dictionary mapping gml:id values to XML elements

    Example:
        >>> tree = ET.parse("city.gml")
        >>> root = tree.getroot()
        >>> id_index = build_id_index(root)
        >>> len(id_index)
        15432
        >>> 'POLY_123' in id_index
        True

    Performance:
        - Time complexity: O(n) where n is the number of elements in the document
        - Space complexity: O(m) where m is the number of elements with gml:id attributes
        - For a typical PLATEAU file with ~10,000 buildings: ~0.1-0.5 seconds
    """
    id_index: Dict[str, ET.Element] = {}

    # Iterate through all elements in the document
    for elem in root.iter():
        # Check for gml:id attribute
        gml_id = elem.get(f"{{{NS['gml']}}}id")
        if gml_id:
            id_index[gml_id] = elem

    return id_index


def resolve_xlink(
    elem: ET.Element,
    id_index: Dict[str, ET.Element],
    debug: bool = False
) -> Optional[ET.Element]:
    """
    Resolve an XLink reference (xlink:href) to the target element.

    XLink references are in the form "#id" or "id", where "id" is a gml:id
    value in the document. This function looks up the target element in the
    ID index.

    Args:
        elem: Element that may contain an xlink:href attribute
        id_index: Index of gml:id → element mappings (from build_id_index())
        debug: Enable debug output for XLink resolution failures

    Returns:
        The target element if reference is resolved, None otherwise

    Example:
        >>> # XML structure:
        >>> # <gml:surfaceMember xlink:href="#POLY_123"/>
        >>> # ...
        >>> # <gml:Polygon gml:id="POLY_123">...</gml:Polygon>
        >>> surface_member = root.find(".//gml:surfaceMember", NS)
        >>> polygon = resolve_xlink(surface_member, id_index)
        >>> polygon.tag
        '{http://www.opengis.net/gml}Polygon'

    Notes:
        - If the element does not have an xlink:href attribute, returns None
        - If the reference cannot be resolved, logs debug info if debug=True
        - Leading '#' is automatically stripped from href values
    """
    # Check for xlink:href attribute
    href = elem.get(f"{{{NS['xlink']}}}href")
    if not href:
        return None

    # Remove leading '#' from href
    if href.startswith("#"):
        target_id = href[1:]
    else:
        target_id = href

    # Look up in index
    result = id_index.get(target_id)

    if debug and result is None:
        # XLink resolution failed - provide helpful debug info
        log(f"      [XLink] Failed to resolve: {href}")
        log(f"      [XLink] Looking for ID: '{target_id}'")

        # Check for similar IDs (helpful for debugging typos or mismatches)
        similar_ids = [
            id_val for id_val in id_index.keys()
            if target_id in id_val or id_val in target_id
        ]
        if similar_ids:
            log(f"      [XLink] Similar IDs found: {similar_ids[:3]}")
        else:
            log(f"      [XLink] No similar IDs found in index")

    return result


def extract_polygon_with_xlink(
    elem: ET.Element,
    id_index: Dict[str, ET.Element],
    debug: bool = False
) -> Optional[ET.Element]:
    """
    Extract a gml:Polygon from an element, resolving XLink references if needed.

    This is a common pattern in CityGML where geometry can be either:
    1. Directly embedded in the element
    2. Referenced via XLink (xlink:href="#polygon_id")

    This function tries both methods automatically.

    Args:
        elem: Element that may contain a Polygon directly or via XLink
        id_index: Index for resolving XLink references (from build_id_index())
        debug: Enable debug output for XLink resolution

    Returns:
        gml:Polygon element or None if not found

    Example:
        >>> # Direct polygon (embedded)
        >>> # <gml:surfaceMember>
        >>> #   <gml:Polygon>...</gml:Polygon>
        >>> # </gml:surfaceMember>
        >>> surface_member = root.find(".//gml:surfaceMember", NS)
        >>> polygon = extract_polygon_with_xlink(surface_member, id_index)

        >>> # XLink reference
        >>> # <gml:surfaceMember xlink:href="#POLY_123"/>
        >>> # ...
        >>> # <gml:Polygon gml:id="POLY_123">...</gml:Polygon>
        >>> surface_member = root.find(".//gml:surfaceMember", NS)
        >>> polygon = extract_polygon_with_xlink(surface_member, id_index)

    Resolution Strategy:
        1. Try to find gml:Polygon directly in element's descendants
        2. If not found, try to resolve XLink reference
        3. If XLink resolves:
           a. Check if target element IS a Polygon
           b. Otherwise, search for Polygon in target's descendants
        4. Return None if all strategies fail
    """
    # Strategy 1: Try to find Polygon directly
    poly = elem.find(".//gml:Polygon", NS)
    if poly is not None:
        return poly

    # Strategy 2: Try to resolve XLink
    target = resolve_xlink(elem, id_index, debug=debug)
    if target is not None:
        # Check if target IS a Polygon element itself
        if target.tag == f"{{{NS['gml']}}}Polygon":
            return target

        # Otherwise, try to find Polygon in target's descendants
        poly = target.find(".//gml:Polygon", NS)
        if poly is not None:
            return poly

    return None
