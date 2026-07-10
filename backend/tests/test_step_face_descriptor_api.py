import pytest
from fastapi import HTTPException

from api.routers.step import _parse_source_face_descriptors


def test_source_face_descriptors_parse_without_texture_mappings():
    descriptors = _parse_source_face_descriptors(
        '[{"nodeIndex":0,"faceIndex":2,"faceNumber":3,'
        '"centroid":[1,2,3],"normal":[0,0,1],"area":4}]'
    )

    assert descriptors[0]["faceNumber"] == 3


@pytest.mark.parametrize("value", ['{}', 'not-json'])
def test_invalid_source_face_descriptors_return_400(value):
    with pytest.raises(HTTPException) as error:
        _parse_source_face_descriptors(value)

    assert error.value.status_code == 400
