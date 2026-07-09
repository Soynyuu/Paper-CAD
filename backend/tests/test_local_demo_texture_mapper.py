import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import services.plateau_texture_mapper as texture_mapper


def test_local_demo_texture_resolution_skips_remote_http(monkeypatch):
    monkeypatch.setenv("ENV", "local_demo")

    def fail_request(*_args, **_kwargs):
        raise AssertionError("local_demo must not fetch remote texture images")

    monkeypatch.setattr(texture_mapper.requests, "get", fail_request)

    data_uri, resolved = texture_mapper._resolve_image_data_uri(
        "https://example.invalid/texture.png",
        "image/png",
        ["https://example.invalid/model.gml"],
    )

    assert data_uri is None
    assert resolved is None


def test_local_demo_texture_resolution_reads_local_relative_image(tmp_path, monkeypatch):
    monkeypatch.setenv("ENV", "local_demo")
    gml_path = tmp_path / "udx" / "bldg" / "53394611_bldg_6697_op.gml"
    image_path = gml_path.parent / "appearance" / "wall.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"png-data")
    gml_path.write_text("<CityModel />", encoding="utf-8")

    data_uri, resolved = texture_mapper._resolve_image_data_uri(
        "appearance/wall.png",
        "image/png",
        [str(gml_path)],
    )

    assert data_uri == f"data:image/png;base64,{base64.b64encode(b'png-data').decode('ascii')}"
    assert resolved == str(image_path)
