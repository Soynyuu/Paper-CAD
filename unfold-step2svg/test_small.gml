<?xml version="1.0" encoding="UTF-8"?>
<core:CityModel xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:core="http://www.opengis.net/citygml/2.0" xmlns:bldg="http://www.opengis.net/citygml/building/2.0" xmlns:gml="http://www.opengis.net/gml">
  <gml:boundedBy>
    <gml:Envelope srsName="http://www.opengis.net/def/crs/EPSG/0/6697" srsDimension="3">
      <gml:lowerCorner>35.0 135.0 0.0</gml:lowerCorner>
      <gml:upperCorner>35.1 135.1 100.0</gml:upperCorner>
    </gml:Envelope>
  </gml:boundedBy>
  <core:cityObjectMember>
    <bldg:Building gml:id="building_1">
      <bldg:measuredHeight uom="m">10.0</bldg:measuredHeight>
      <bldg:lod0FootPrint>
        <gml:MultiSurface>
          <gml:surfaceMember>
            <gml:Polygon>
              <gml:exterior>
                <gml:LinearRing>
                  <gml:posList>0 0 0 10 0 0 10 10 0 0 10 0 0 0 0</gml:posList>
                </gml:LinearRing>
              </gml:exterior>
            </gml:Polygon>
          </gml:surfaceMember>
        </gml:MultiSurface>
      </bldg:lod0FootPrint>
    </bldg:Building>
  </core:cityObjectMember>
</core:CityModel>