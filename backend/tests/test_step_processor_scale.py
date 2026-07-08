import pytest

from models.request_models import BrepPapercraftRequest
from services.step_processor import StepUnfoldGenerator


def _rect(width: float, height: float):
    return [(0.0, 0.0), (width, 0.0), (width, height), (0.0, height)]


def test_fixed_scale_converts_unfolded_groups_to_paper_dimensions():
    generator = StepUnfoldGenerator()
    generator.apply_request_settings(
        BrepPapercraftRequest(
            layout_mode="paged",
            page_format="A4",
            page_orientation="portrait",
            scale_factor=150.0,
            scale_mode="fixed",
        )
    )

    groups, warnings = generator._prepare_groups_for_layout(
        [{"polygons": [_rect(15000.0, 3000.0)], "tabs": [_rect(1500.0, 300.0)]}]
    )

    bbox = groups[0]["bbox"]
    assert bbox["width"] == pytest.approx(100.0)
    assert bbox["height"] == pytest.approx(20.0)
    assert groups[0]["tabs"][0][1][0] == pytest.approx(10.0)
    assert warnings == []
    assert generator.stats["scale_mode"] == "fixed"
    assert generator.stats["applied_scale_factor"] == pytest.approx(150.0)
    assert generator.stats["source_units"] == "mm"


def test_fixed_scale_converts_meter_inputs_to_paper_millimeters():
    generator = StepUnfoldGenerator()
    generator.apply_request_settings(
        BrepPapercraftRequest(
            layout_mode="paged",
            page_format="A4",
            page_orientation="portrait",
            scale_factor=150.0,
            scale_mode="fixed",
            units="m",
        )
    )

    groups, warnings = generator._prepare_groups_for_layout(
        [{"polygons": [_rect(15.0, 3.0)], "tabs": [_rect(1.5, 0.3)]}]
    )

    bbox = groups[0]["bbox"]
    assert bbox["width"] == pytest.approx(100.0)
    assert bbox["height"] == pytest.approx(20.0)
    assert groups[0]["tabs"][0][1][0] == pytest.approx(10.0)
    assert warnings == []
    assert generator.stats["source_units"] == "m"
    assert generator.stats["unit_to_mm_factor"] == pytest.approx(1000.0)


def test_fit_page_scale_uses_selected_page_orientation():
    generator = StepUnfoldGenerator()
    groups = [{"polygons": [_rect(3000.0, 1000.0)], "tabs": []}]

    generator.apply_request_settings(
        BrepPapercraftRequest(
            layout_mode="paged",
            page_format="A4",
            page_orientation="portrait",
            scale_factor=150.0,
            scale_mode="fit_page",
        )
    )
    portrait_groups, portrait_warnings = generator._prepare_groups_for_layout(groups)
    portrait_scale = generator.applied_scale_factor
    portrait_printable_height = generator.layout_manager.printable_height_mm

    generator.apply_request_settings(
        BrepPapercraftRequest(
            layout_mode="paged",
            page_format="A4",
            page_orientation="landscape",
            scale_factor=150.0,
            scale_mode="fit_page",
        )
    )
    landscape_groups, landscape_warnings = generator._prepare_groups_for_layout(groups)
    landscape_scale = generator.applied_scale_factor
    landscape_printable_width = generator.layout_manager.printable_width_mm

    assert portrait_groups[0]["bbox"]["width"] == pytest.approx(portrait_printable_height)
    assert landscape_groups[0]["bbox"]["width"] == pytest.approx(landscape_printable_width)
    assert portrait_warnings[0]["type"] == "fit_page_scale_applied"
    assert landscape_warnings[0]["type"] == "fit_page_scale_applied"
    assert portrait_scale < 3000.0 / generator.layout_manager.page_sizes_mm["A4"]["width"]
    assert landscape_scale == pytest.approx(portrait_scale)


def test_fit_page_scale_respects_meter_units():
    generator = StepUnfoldGenerator()
    groups = [{"polygons": [_rect(30.0, 10.0)], "tabs": []}]

    generator.apply_request_settings(
        BrepPapercraftRequest(
            layout_mode="paged",
            page_format="A4",
            page_orientation="portrait",
            scale_factor=150.0,
            scale_mode="fit_page",
            units="m",
        )
    )
    paper_groups, warnings = generator._prepare_groups_for_layout(groups)

    assert paper_groups[0]["bbox"]["width"] == pytest.approx(
        generator.layout_manager.printable_height_mm
    )
    assert warnings[0]["type"] == "fit_page_scale_applied"
    assert generator.stats["applied_scale_factor"] == pytest.approx(
        30000.0 / generator.layout_manager.printable_height_mm
    )


def test_fit_page_scale_uses_largest_single_group_not_single_page_packing():
    generator = StepUnfoldGenerator()
    groups = [
        {"polygons": [_rect(1000.0, 1000.0)], "tabs": []},
        {"polygons": [_rect(1000.0, 1000.0)], "tabs": []},
    ]

    generator.apply_request_settings(
        BrepPapercraftRequest(
            layout_mode="paged",
            page_format="A4",
            page_orientation="portrait",
            scale_factor=150.0,
            scale_mode="fit_page",
        )
    )
    paper_groups, warnings = generator._prepare_groups_for_layout(groups)

    individual_only_scale = 1000.0 / generator.layout_manager.printable_width_mm
    assert generator.applied_scale_factor == pytest.approx(individual_only_scale)
    assert not generator.layout_manager.can_pack_groups_on_single_page(paper_groups)
    assert warnings[0]["type"] == "fit_page_scale_applied"
