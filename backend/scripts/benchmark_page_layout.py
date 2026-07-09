#!/usr/bin/env python3
"""Benchmark page packing with unfolded groups from a STEP file or cache."""

import argparse
import copy
import json
import logging
import pickle
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from core.layout_manager import LayoutManager  # noqa: E402
from models.request_models import BrepPapercraftRequest  # noqa: E402
from services.step_processor import StepUnfoldGenerator  # noqa: E402


def polygon_area(points):
    return abs(
        sum(
            x1 * y2 - x2 * y1
            for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1])
        )
        / 2.0
    )


def prepare_groups(step_path, cache_path):
    generator = StepUnfoldGenerator()
    if not generator.load_from_file(str(step_path)):
        raise RuntimeError(f"Failed to load STEP file: {step_path}")

    request = BrepPapercraftRequest(
        layout_mode="paged",
        page_format="A4",
        page_orientation="portrait",
        scale_factor=150,
        scale_mode="fit_page",
        units="m",
        max_faces=20,
        merge_mode="improved",
    )
    generator.apply_request_settings(request)
    generator.analyze_brep_topology()
    generator.group_faces_for_unfolding(request.max_faces)
    unfolded_groups = generator.unfold_face_groups()
    paper_groups, warnings = generator._prepare_groups_for_layout(unfolded_groups)

    with cache_path.open("wb") as cache_file:
        pickle.dump(paper_groups, cache_file)
    return paper_groups, warnings


def layout_metrics(manager, pages, elapsed):
    page_area = manager.printable_width_mm * manager.printable_height_mm
    page_metrics = []
    for page in pages:
        shape_area = sum(
            polygon_area(polygon)
            for group in page
            for polygon in group.get("polygons", [])
        )
        bbox_area = sum(
            group["bbox"]["width"] * group["bbox"]["height"] for group in page
        )
        page_metrics.append(
            {
                "groups": len(page),
                "shape_utilization": round(shape_area / page_area, 4),
                "bbox_utilization": round(bbox_area / page_area, 4),
            }
        )

    return {
        "groups": sum(len(page) for page in pages),
        "pages": len(pages),
        "seconds": round(elapsed, 3),
        "mean_shape_utilization": round(
            sum(item["shape_utilization"] for item in page_metrics)
            / max(len(page_metrics), 1),
            4,
        ),
        "page_metrics": page_metrics,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", type=Path)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--margin", type=float, default=3.0)
    parser.add_argument("--polygon-limit", type=int, default=10)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if not args.verbose:
        logging.disable(logging.INFO)

    prepare_seconds = 0.0
    warnings = []
    if args.cache.exists():
        with args.cache.open("rb") as cache_file:
            groups = pickle.load(cache_file)
    else:
        if args.step is None:
            parser.error("--step is required when --cache does not exist")
        started = time.perf_counter()
        groups, warnings = prepare_groups(args.step, args.cache)
        prepare_seconds = time.perf_counter() - started

    manager = LayoutManager(page_format="A4", page_orientation="portrait")
    manager.page_item_margin_mm = args.margin
    manager.polygon_fit_occupancy_limit = args.polygon_limit
    started = time.perf_counter()
    pages, layout_warnings = manager.layout_for_pages(copy.deepcopy(groups))
    elapsed = time.perf_counter() - started

    result = layout_metrics(manager, pages, elapsed)
    result["prepare_seconds"] = round(prepare_seconds, 3)
    result["warnings"] = len(warnings) + len(layout_warnings)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
