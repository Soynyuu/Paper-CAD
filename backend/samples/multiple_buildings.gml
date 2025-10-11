<?xml version="1.0" encoding="UTF-8"?>
<core:CityModel
    xmlns:gml="http://www.opengis.net/gml"
    xmlns:core="http://www.opengis.net/citygml/2.0"
    xmlns:bldg="http://www.opengis.net/citygml/building/2.0"
    xmlns:gen="http://www.opengis.net/citygml/generics/2.0"
    xmlns:uro="http://www.opengis.net/uro/1.0"
    gml:id="cm_test">
  <core:cityObjectMember>
    <bldg:Building gml:id="bldg_001">
      <bldg:measuredHeight>12.5</bldg:measuredHeight>
      <gen:stringAttribute name="buildingID">
        <gen:value>TEST-001</gen:value>
      </gen:stringAttribute>
      <bldg:lod0FootPrint>
        <gml:Polygon gml:id="fp_001">
          <gml:exterior>
            <gml:LinearRing>
              <gml:posList>
                0 0
                10 0
                10 10
                0 10
                0 0
              </gml:posList>
            </gml:LinearRing>
          </gml:exterior>
        </gml:Polygon>
      </bldg:lod0FootPrint>
    </bldg:Building>
  </core:cityObjectMember>
  <core:cityObjectMember>
    <bldg:Building gml:id="bldg_002">
      <bldg:measuredHeight>15.0</bldg:measuredHeight>
      <gen:stringAttribute name="buildingID">
        <gen:value>TEST-002</gen:value>
      </gen:stringAttribute>
      <bldg:lod0FootPrint>
        <gml:Polygon gml:id="fp_002">
          <gml:exterior>
            <gml:LinearRing>
              <gml:posList>
                20 0
                30 0
                30 10
                20 10
                20 0
              </gml:posList>
            </gml:LinearRing>
          </gml:exterior>
        </gml:Polygon>
      </bldg:lod0FootPrint>
    </bldg:Building>
  </core:cityObjectMember>
  <core:cityObjectMember>
    <bldg:Building gml:id="bldg_003">
      <bldg:measuredHeight>18.0</bldg:measuredHeight>
      <gen:stringAttribute name="buildingID">
        <gen:value>TEST-003</gen:value>
      </gen:stringAttribute>
      <bldg:lod0FootPrint>
        <gml:Polygon gml:id="fp_003">
          <gml:exterior>
            <gml:LinearRing>
              <gml:posList>
                40 0
                50 0
                50 10
                40 10
                40 0
              </gml:posList>
            </gml:LinearRing>
          </gml:exterior>
        </gml:Polygon>
      </bldg:lod0FootPrint>
    </bldg:Building>
  </core:cityObjectMember>
</core:CityModel>
