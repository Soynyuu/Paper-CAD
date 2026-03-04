import asyncio
import os
import tempfile
import uuid
from functools import partial
from typing import Any, Dict, Optional, Union

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException
from fastapi.responses import FileResponse

from api.helpers import cleanup_temp_dir, normalize_limit_param, parse_csv_ids
from config import OCCT_AVAILABLE
from models.request_models import (
    BuildingIdWithMeshItem,
    BuildingInfoResponse,
    GeocodingResultResponse,
    MeshToTilesetsRequest,
    MeshToTilesetsResponse,
    PlateauBatchBuildingRequest,
    PlateauBatchBuildingResponse,
    PlateauBuildingIdRequest,
    PlateauBuildingIdSearchResponse,
    PlateauBuildingIdWithMeshRequest,
    PlateauTexturedUnfoldRequest,
    PlateauSearchRequest,
    PlateauSearchResponse,
    TilesetInfo,
    BrepPapercraftRequest,
)
from services.citygml import export_step_from_citygml
from services.plateau_api_client import (
    fetch_plateau_dataset_by_municipality,
    fetch_tilesets_for_meshes,
)
from services.plateau_fetcher import (
    search_building_by_id,
    search_building_by_id_and_mesh,
    search_buildings_by_address,
)
from services.plateau_texture_mapper import build_plateau_texture_mappings
from services.step_processor import StepUnfoldGenerator

router = APIRouter()


# --- PLATEAU Address Search ---
@router.post(
    "/api/plateau/search-by-address",
    summary="PLATEAU Building Search by Address",
    tags=["PLATEAU Integration"],
    response_model=PlateauSearchResponse,
    responses={
        200: {
            "description": "Building search results with geocoding and distance sorting",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "geocoding": {
                            "query": "東京駅",
                            "latitude": 35.681236,
                            "longitude": 139.767125,
                            "display_name": "Tokyo Station, Tokyo, Japan",
                        },
                        "buildings": [
                            {
                                "building_id": "13101-bldg-12345",
                                "gml_id": "bldg_a1234",
                                "latitude": 35.681300,
                                "longitude": 139.767200,
                                "distance_meters": 10.5,
                                "height": 45.0,
                                "usage": "商業施設",
                                "name": "東京駅丸の内ビル",
                                "has_lod2": True,
                            }
                        ],
                        "found_count": 15,
                        "search_mode": "hybrid",
                    }
                }
            },
        },
        400: {"description": "Invalid search parameters"},
        500: {"description": "Geocoding or PLATEAU API error"},
    },
)
async def plateau_search_by_address(request: PlateauSearchRequest):
    """
    住所または施設名からPLATEAU建物を検索します。

    Search for PLATEAU buildings by address or facility name.

    **処理フロー / Process Flow**:
    1. OpenStreetMap Nominatim APIで住所→座標変換 / Geocoding via OSM Nominatim
    2. PLATEAU Data Catalog APIから周辺のCityGMLデータを取得 / Fetch nearby CityGML data
    3. 建物情報を抽出・パース / Extract and parse building information
    4. 距離・名前類似度でソート / Sort by distance and name similarity

    **入力例 / Example Inputs**:
    - 施設名 / Facility name: "東京駅", "渋谷スクランブルスクエア"
    - 完全住所 / Full address: "東京都千代田区丸の内1-9-1"
    - 部分住所 / Partial address: "千代田区丸の内"
    - 郵便番号 / Postal code: "100-0005"

    **検索モード / Search Modes**:
    - `distance`: 距離優先 / Distance-based ranking
    - `name`: 名前類似度優先 / Name similarity ranking
    - `hybrid`: 距離+名前の複合スコア / Combined distance + name score (default)

    **レート制限 / Rate Limits**:
    - Nominatim: 1リクエスト/秒（自動的に適用） / 1 req/sec (auto-enforced)

    Example:
        ```json
        {
            "query": "東京駅",
            "radius": 0.001,
            "limit": 10
        }
        ```
    """
    try:
        print(f"\n{'=' * 60}")
        print(f"[API] /api/plateau/search-by-address")
        print(f"[API] Query: {request.query}")
        print(f"[API] Radius: {request.radius} degrees")
        print(f"[API] Limit: {request.limit}")
        print(f"{'=' * 60}\n")

        # Call the search function with name_filter and search_mode
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                search_buildings_by_address,
                query=request.query,
                radius=request.radius,
                limit=request.limit,
                name_filter=request.name_filter,
                search_mode=request.search_mode or "hybrid",
            ),
        )

        if not result["success"]:
            # Return error response
            return PlateauSearchResponse(
                success=False,
                geocoding=None,
                buildings=[],
                found_count=0,
                search_mode=result.get("search_mode", "hybrid"),
                error=result.get("error", "Unknown error"),
            )

        # Convert to response models
        geocoding_data = result["geocoding"]
        geocoding_response = (
            GeocodingResultResponse(
                query=geocoding_data.query,
                latitude=geocoding_data.latitude,
                longitude=geocoding_data.longitude,
                display_name=geocoding_data.display_name,
                osm_type=geocoding_data.osm_type,
                osm_id=geocoding_data.osm_id,
            )
            if geocoding_data
            else None
        )

        buildings_response = [
            BuildingInfoResponse(
                building_id=b.building_id,
                gml_id=b.gml_id,
                latitude=b.latitude,
                longitude=b.longitude,
                distance_meters=b.distance_meters,
                height=b.height,
                usage=b.usage,
                measured_height=b.measured_height,
                name=b.name,
                relevance_score=b.relevance_score,
                name_similarity=b.name_similarity,
                match_reason=b.match_reason,
                has_lod2=b.has_lod2,
                has_lod3=b.has_lod3,
            )
            for b in result["buildings"]
        ]

        return PlateauSearchResponse(
            success=True,
            geocoding=geocoding_response,
            buildings=buildings_response,
            found_count=len(buildings_response),
            search_mode=result.get("search_mode", "hybrid"),
            error=None,
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"検索エラー: {str(e)}")


@router.post(
    "/api/plateau/fetch-and-convert",
    summary="PLATEAU Fetch & Convert (One-Step)",
    tags=["PLATEAU Integration"],
    responses={
        200: {
            "description": "STEP file generated from PLATEAU data",
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"},
                    "example": "STEP file from PLATEAU building",
                }
            },
        },
        400: {"description": "Invalid parameters or building_ids format"},
        500: {"description": "Geocoding, PLATEAU API, or conversion error"},
    },
)
async def plateau_fetch_and_convert(
    background_tasks: BackgroundTasks,
    query: str = Form(
        ..., description="住所または施設名 / Address or facility name (e.g., '東京駅')"
    ),
    radius: float = Form(
        0.001, description="検索半径（度、約100m） / Search radius in degrees (~100m)"
    ),
    auto_select_nearest: bool = Form(
        True, description="最近傍建物を自動選択 / Auto-select nearest building"
    ),
    building_limit: Union[int, str, None] = Form(
        None, description="変換する建物数（未指定で無制限） / Max buildings to convert"
    ),
    building_ids: Optional[str] = Form(
        None,
        description="ユーザー選択の建物IDリスト（カンマ区切り） / User-selected building IDs (comma-separated)",
    ),
    debug: bool = Form(False, description="デバッグモード / Debug mode"),
    method: str = Form(
        "solid", description="変換方式 / Conversion method (solid/auto/sew/extrude)"
    ),
    auto_reproject: bool = Form(
        True, description="自動再投影 / Auto-reproject to planar CRS"
    ),
    precision_mode: str = Form(
        "ultra",
        description="精度モード / Precision mode (standard/high/maximum/ultra, recommended: ultra)",
    ),
    shape_fix_level: str = Form(
        "minimal",
        description="形状修正レベル / Shape fix level (minimal/standard/aggressive/ultra, recommended: minimal)",
    ),
    merge_building_parts: bool = Form(
        False,
        description="BuildingPart結合 / Merge BuildingPart (False recommended for detail preservation)",
    ),
):
    """
    住所・施設名から自動的にPLATEAU建物を取得してSTEPファイルに変換します。

    Automatically fetch PLATEAU buildings by address/facility name and convert to STEP.

    **ワンステップ処理 / One-Step Process**:
    1. 住所検索（Nominatim） / Geocoding via Nominatim
    2. CityGML取得（PLATEAU API） ← 1回のみ / Fetch CityGML once
    3. 最近傍建物特定 / Identify nearest building
    4. STEP変換（取得済みCityGMLを再利用） / Convert to STEP (reuse fetched data)
    5. ファイル返却 / Return STEP file

    **入力例 / Example**:
    - query: "東京駅" (Tokyo Station)
    - radius: 0.001 (約100m / ~100m)
    - building_limit: 1 (最近傍の1棟のみ / nearest building only)

    **建物選択 / Building Selection**:
    - `auto_select_nearest=True` + `building_ids=None`: 最近傍N棟を自動選択 / Auto-select N nearest buildings
    - `building_ids="id1,id2"`: ユーザー指定の建物のみ変換 / Convert only user-specified buildings

    **利点 / Benefits**:
    - ✅ CityGMLファイルの手動ダウンロード不要 / No manual CityGML download required
    - ✅ 必要な建物のみを取得（軽量） / Fetch only needed buildings (lightweight)
    - ✅ 常に最新のPLATEAUデータを使用 / Always uses latest PLATEAU data
    - ✅ 1回のAPIコールで完結 / Single API call workflow
    """
    tmpdir = None
    out_dir = None
    success = False
    try:
        # Normalize building_limit parameter (handle empty string, "0", or None)
        normalized_building_limit = normalize_limit_param(
            building_limit, param_name="building_limit"
        )

        # Normalize building_ids parameter (comma-separated string to list)
        normalized_building_ids = parse_csv_ids(building_ids)

        print(f"\n{'=' * 60}")
        print(f"[API] /api/plateau/fetch-and-convert")
        print(f"[API] Query: {query}")
        print(f"[API] Radius: {radius} degrees")
        print(
            f"[API] Building limit: {normalized_building_limit if normalized_building_limit else 'unlimited'}"
        )
        print(
            f"[API] User-selected building IDs: {normalized_building_ids if normalized_building_ids else 'None (auto-select)'}"
        )
        print(f"{'=' * 60}\n")

        # Step 1: Search for buildings
        loop = asyncio.get_event_loop()
        search_result = await loop.run_in_executor(
            None,
            partial(
                search_buildings_by_address,
                query=query,
                radius=radius,
                limit=normalized_building_limit if auto_select_nearest else None,
            ),
        )

        if not search_result["success"]:
            raise HTTPException(
                status_code=404,
                detail=search_result.get("error", "建物が見つかりませんでした"),
            )

        buildings = search_result["buildings"]
        if not buildings:
            raise HTTPException(
                status_code=404,
                detail=f"指定された場所に建物が見つかりませんでした: {query}",
            )

        # Step 2: Extract gml:id list from user selection OR smart-selected buildings
        if normalized_building_ids:
            # User explicitly selected specific buildings - use those IDs directly
            final_building_ids = normalized_building_ids
            print(f"[API] Using {len(final_building_ids)} user-selected building(s):")

            # Find LOD information for selected buildings
            for i, bid in enumerate(final_building_ids, 1):
                # Find matching building in search results to get LOD info
                matching_building = next(
                    (b for b in buildings if b.gml_id == bid), None
                )
                if matching_building:
                    lod_str = []
                    if matching_building.has_lod3:
                        lod_str.append("LOD3")
                    if matching_building.has_lod2:
                        lod_str.append("LOD2")
                    if not lod_str:
                        lod_str.append("LOD1 or lower")

                    height = (
                        matching_building.measured_height
                        or matching_building.height
                        or 0
                    )
                    name_str = (
                        f'"{matching_building.name}"'
                        if matching_building.name
                        else "unnamed"
                    )
                    print(f"[API LOD INFO]   {i}. {name_str} ({', '.join(lod_str)})")
                    print(f"[API LOD INFO]      ID: {bid[:50]}...")
                    print(
                        f"[API LOD INFO]      Height: {height:.1f}m, Distance: {matching_building.distance_meters:.1f}m"
                    )
                else:
                    print(f"[API]   {i}. {bid[:50]}... (LOD info unavailable)")
        else:
            # No user selection - fall back to auto-selection from search results
            selected_buildings = (
                buildings[:normalized_building_limit]
                if normalized_building_limit
                else buildings
            )
            final_building_ids = [
                b.gml_id for b in selected_buildings
            ]  # Always use gml:id

            print(
                f"[API] Auto-selected {len(final_building_ids)} building(s) by smart scoring:"
            )
            for i, (bid, b) in enumerate(
                zip(final_building_ids, selected_buildings), 1
            ):
                lod_str = []
                if b.has_lod3:
                    lod_str.append("LOD3")
                if b.has_lod2:
                    lod_str.append("LOD2")
                if not lod_str:
                    lod_str.append("LOD1 or lower")

                height = b.measured_height or b.height or 0
                name_str = f'"{b.name}"' if b.name else "unnamed"
                print(
                    f"[API LOD INFO]   {i}. {name_str} ({', '.join(lod_str)}) - {height:.1f}m, {b.distance_meters:.1f}m away"
                )
                print(f"[API LOD INFO]      ID: {bid[:30]}...")

        # Step 3: Reuse CityGML XML from search results (no re-fetch needed!)
        xml_content = search_result.get("citygml_xml")

        if not xml_content:
            raise HTTPException(
                status_code=500, detail="CityGMLデータの取得に失敗しました"
            )

        print(f"[API] Reusing CityGML from search results ({len(xml_content):,} bytes)")

        # Step 4: Save CityGML to temp file
        tmpdir = tempfile.mkdtemp()
        gml_path = os.path.join(tmpdir, f"{uuid.uuid4()}.gml")
        with open(gml_path, "w", encoding="utf-8") as f:
            f.write(xml_content)

        # Step 5: Convert to STEP with gml:id filtering
        out_dir = tempfile.mkdtemp()
        # Use ASCII-safe filename (HTTP headers don't support non-ASCII characters)
        output_filename = "plateau_building.step"
        out_path = os.path.join(out_dir, output_filename)

        ok, msg = await loop.run_in_executor(
            None,
            partial(
                export_step_from_citygml,
                gml_path,
                out_path,
                limit=None,  # Don't use limit - we filter by building_ids instead
                debug=debug,
                method=method,
                auto_reproject=auto_reproject,
                precision_mode=precision_mode,
                shape_fix_level=shape_fix_level,
                merge_building_parts=merge_building_parts,
                # Use gml:id filtering (consistent, no mixed ID types)
                building_ids=final_building_ids,
                filter_attribute="gml:id",
            ),
        )

        if not ok:
            raise HTTPException(
                status_code=500, detail=f"STEP変換に失敗しました: {msg}"
            )

        # Step 6: Return STEP file
        file_size = os.path.getsize(out_path)
        print(f"[API] Success: Generated {output_filename} ({file_size:,} bytes)")

        # Cleanup function
        def cleanup_temp_files():
            try:
                if os.path.exists(gml_path):
                    os.remove(gml_path)
                if os.path.exists(tmpdir):
                    os.rmdir(tmpdir)
                if os.path.exists(out_path):
                    os.remove(out_path)
                if os.path.exists(out_dir):
                    os.rmdir(out_dir)
                print(f"[CLEANUP] Removed temporary files")
            except Exception as e:
                print(f"[CLEANUP] Failed: {e}")

        background_tasks.add_task(cleanup_temp_files)

        success = True
        return FileResponse(
            path=out_path,
            media_type="application/octet-stream",
            filename=output_filename,
            headers={"Cache-Control": "no-cache"},
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"予期しないエラー: {str(e)}")
    finally:
        # エラー時の一時ディレクトリクリーンアップ
        # 成功時はbackground_tasksが処理するため、エラー時のみクリーンアップ
        if not success:
            cleanup_temp_dir(tmpdir, label="tmpdir")
            cleanup_temp_dir(out_dir, label="out_dir")


# --- PLATEAU: Building ID Search ---
@router.post(
    "/api/plateau/search-by-id",
    summary="PLATEAU Building Search by ID",
    tags=["PLATEAU Integration"],
    response_model=PlateauBuildingIdSearchResponse,
    responses={
        200: {
            "description": "Building information retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "building": {
                            "building_id": "13101-bldg-2287",
                            "gml_id": "bldg_a1234",
                            "latitude": 35.681236,
                            "longitude": 139.767125,
                            "height": 45.0,
                            "has_lod2": True,
                        },
                        "municipality_code": "13101",
                        "municipality_name": "千代田区",
                        "citygml_file": "udx/bldg/13101_tokyo23-ku_2020_citygml_3_op/bldg_53394611_op.gml",
                    }
                }
            },
        },
        400: {"description": "Invalid building ID format"},
        404: {"description": "Building not found in PLATEAU Data Catalog"},
        500: {"description": "PLATEAU API error or parsing error"},
    },
)
async def plateau_search_by_building_id(request: PlateauBuildingIdRequest):
    """
    建物IDから特定のPLATEAU建物を検索します。

    Search for a specific PLATEAU building by its building ID.

    **建物ID形式 / Building ID Format**:
    - PLATEAU標準: `{市区町村コード}-bldg-{連番}` (例: "13101-bldg-2287")
    - 市区町村コード: 5桁の自治体コード (例: 13101 = 千代田区)

    **処理フロー / Process Flow**:
    1. 建物IDから市区町村コードを抽出 / Extract municipality code from building ID
    2. PLATEAU APIで該当する市区町村のCityGMLファイルを検索 / Search CityGML files for the municipality
    3. ファイルをダウンロードして建物を検索 / Download and search for the building
    4. 建物情報を返却 / Return building information

    **入力例 / Example Input**:
    ```json
    {
        "building_id": "13101-bldg-2287"
    }
    ```

    **特徴 / Features**:
    - 完全なファイルダウンロード不要（軽量検索） / Lightweight search without full file download
    - 市区町村コード自動抽出 / Automatic municipality code extraction
    - CityGMLファイル情報を返却 / Returns CityGML file information
    """
    try:
        print(f"\n{'=' * 60}")
        print(f"[API] /api/plateau/search-by-id")
        print(f"[API] Building ID: {request.building_id}")
        print(f"{'=' * 60}\n")

        # Search for building by ID
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(search_building_by_id, request.building_id, debug=request.debug),
        )

        if not result["success"]:
            return PlateauBuildingIdSearchResponse(
                success=False,
                building=None,
                municipality_code=result.get("municipality_code"),
                municipality_name=result.get("municipality_name"),
                citygml_file=result.get("citygml_file"),
                total_buildings_in_file=result.get("total_buildings_in_file"),
                error=result.get("error"),
                error_details=result.get("error_details"),
            )

        # Success: Convert BuildingInfo to BuildingInfoResponse
        building_data = result["building"]
        building_response = BuildingInfoResponse(
            building_id=building_data.building_id,
            gml_id=building_data.gml_id,
            latitude=building_data.latitude,
            longitude=building_data.longitude,
            distance_meters=building_data.distance_meters,
            height=building_data.height,
            usage=building_data.usage,
            measured_height=building_data.measured_height,
            name=building_data.name,
            relevance_score=building_data.relevance_score,
            name_similarity=building_data.name_similarity,
            match_reason=building_data.match_reason,
            has_lod2=building_data.has_lod2,
            has_lod3=building_data.has_lod3,
        )

        return PlateauBuildingIdSearchResponse(
            success=True,
            building=building_response,
            municipality_code=result["municipality_code"],
            municipality_name=result["municipality_name"],
            citygml_file=result.get("citygml_file"),
            total_buildings_in_file=result["total_buildings_in_file"],
            error=None,
            error_details=None,
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        return PlateauBuildingIdSearchResponse(
            success=False,
            building=None,
            error="Internal server error",
            error_details=f"予期しないエラー: {str(e)}",
        )


@router.post(
    "/api/plateau/fetch-by-id",
    summary="PLATEAU Fetch & Convert by ID",
    tags=["PLATEAU Integration"],
    responses={
        200: {
            "description": "STEP file generated from PLATEAU building",
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"},
                    "example": "STEP file for building 13101-bldg-2287",
                }
            },
        },
        400: {"description": "Invalid building ID format"},
        404: {"description": "Building not found"},
        500: {"description": "PLATEAU API error or conversion error"},
    },
)
async def plateau_fetch_by_building_id(request: PlateauBuildingIdRequest):
    """
    建物IDから直接PLATEAU建物を取得してSTEP変換します。

    Fetch PLATEAU building by ID and convert to STEP format.

    **ワンステップ処理 / One-Step Process**:
    1. 建物IDで検索 / Search by building ID
    2. CityGML取得 / Fetch CityGML data
    3. STEP変換 / Convert to STEP
    4. ファイル返却 / Return STEP file

    **入力例 / Example Input**:
    ```json
    {
        "building_id": "13101-bldg-2287",
        "precision_mode": "ultra",
        "shape_fix_level": "minimal"
    }
    ```
    """
    if not OCCT_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="OpenCASCADE が利用できません。STEPファイルの変換には OpenCASCADE が必要です。",
        )

    try:
        print(f"\n{'=' * 60}")
        print(f"[API] /api/plateau/fetch-by-id")
        print(f"[API] Building ID: {request.building_id}")
        print(f"[API] Precision Mode: {request.precision_mode}")
        print(f"[API] Shape Fix Level: {request.shape_fix_level}")
        print(f"{'=' * 60}\n")

        # Step 1: Search for building by ID
        loop = asyncio.get_event_loop()
        search_result = await loop.run_in_executor(
            None,
            partial(search_building_by_id, request.building_id, debug=request.debug),
        )

        if not search_result["success"]:
            error_msg = search_result.get("error", "Building not found")
            error_details = search_result.get("error_details", "")
            raise HTTPException(status_code=404, detail=f"{error_msg}. {error_details}")

        # Step 2: Convert to STEP
        citygml_xml = search_result.get("citygml_xml")
        if not citygml_xml:
            raise HTTPException(
                status_code=500, detail="CityGML data is missing from search result"
            )

        # Save CityGML to temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".gml", delete=False, encoding="utf-8"
        ) as tmp_gml:
            tmp_gml.write(citygml_xml)
            tmp_gml_path = tmp_gml.name

        # Create temporary STEP output file
        step_file_name = f"{request.building_id.replace('-', '_')}.step"
        tmp_step_path = os.path.join(tempfile.gettempdir(), step_file_name)

        try:
            # Export to STEP with specified building ID filter
            loop = asyncio.get_event_loop()
            success, message = await loop.run_in_executor(
                None,
                partial(
                    export_step_from_citygml,
                    tmp_gml_path,
                    tmp_step_path,
                    building_ids=[request.building_id],
                    filter_attribute="gml:id",
                    method=request.method,
                    auto_reproject=request.auto_reproject,
                    precision_mode=request.precision_mode,
                    shape_fix_level=request.shape_fix_level,
                    merge_building_parts=request.merge_building_parts,
                    debug=request.debug,
                ),
            )

            if not success:
                raise HTTPException(
                    status_code=500,
                    detail=f"CityGML to STEP conversion failed: {message}",
                )

            # Verify STEP file exists
            if not os.path.exists(tmp_step_path):
                raise HTTPException(status_code=500, detail="STEP file was not created")

            # Return STEP file
            print(
                f"[API] Success: Returning STEP file for building {request.building_id}"
            )
            return FileResponse(
                path=tmp_step_path,
                media_type="application/octet-stream",
                filename=step_file_name,
                background=BackgroundTasks(),
            )

        finally:
            # Clean up temporary CityGML file
            if os.path.exists(tmp_gml_path):
                os.remove(tmp_gml_path)

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"予期しないエラー: {str(e)}")


# --- PLATEAU: Building ID + Mesh Code Search (Optimized) ---
@router.post(
    "/api/plateau/search-by-id-and-mesh",
    summary="PLATEAU Building Search by ID + Mesh (Optimized)",
    tags=["PLATEAU Integration"],
    response_model=PlateauBuildingIdSearchResponse,
    responses={
        200: {
            "description": "Building information from 1km² mesh area (fast)",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "building": {
                            "building_id": "13101-bldg-2287",
                            "gml_id": "bldg_48aa415d-b82f-4e8f-97e1-7538b5cb6c86",
                            "latitude": 35.681236,
                            "longitude": 139.767125,
                            "height": 45.0,
                            "has_lod2": True,
                        },
                        "municipality_code": "13101",
                        "citygml_file": "udx/bldg/13101_tokyo23-ku_2020_citygml_3_op/53394511_bldg_6697_op.gml",
                    }
                }
            },
        },
        400: {"description": "Invalid mesh code format (must be 8 digits)"},
        404: {"description": "Building not found in specified mesh"},
        500: {"description": "PLATEAU API error"},
    },
)
async def plateau_search_by_id_and_mesh(request: PlateauBuildingIdWithMeshRequest):
    """
    建物ID＋メッシュコードで検索（最適化版、高速）。

    Search for a specific PLATEAU building by GML ID + mesh code (optimized, fast).

    **最適化 / Optimization**:
    - ✅ 1km²のメッシュのみダウンロード / Download only 1km² mesh area
    - ✅ 市区町村全体のダウンロード不要 / No need to download entire municipality
    - ⚡ `/api/plateau/search-by-id`より大幅に高速 / Much faster than /search-by-id

    **メッシュコード / Mesh Code**:
    - 3次メッシュコード（8桁、1km区画） / 3rd mesh code (8 digits, 1km area)
    - 例 / Example: "53394511" (東京駅付近)

    **入力例 / Example Input**:
    ```json
    {
        "building_id": "bldg_48aa415d-b82f-4e8f-97e1-7538b5cb6c86",
        "mesh_code": "53394511"
    }
    ```

    **用途 / Use Cases**:
    - メッシュコードが既知の場合の高速検索 / Fast search when mesh code is known
    - 大量建物の一括処理 / Batch processing of many buildings
    """
    try:
        print(f"\n{'=' * 60}")
        print(f"[API] /api/plateau/search-by-id-and-mesh")
        print(f"[API] Building ID: {request.building_id}")
        print(f"[API] Mesh Code: {request.mesh_code}")
        print(f"{'=' * 60}\n")

        # Search for building by ID + mesh code
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                search_building_by_id_and_mesh,
                request.building_id,
                request.mesh_code,
                debug=request.debug,
            ),
        )

        if not result["success"]:
            return PlateauBuildingIdSearchResponse(
                success=False,
                building=None,
                municipality_code=None,  # Not used in mesh-based search
                municipality_name=None,
                citygml_file=None,
                total_buildings_in_file=result.get("total_buildings_in_mesh"),
                error=result.get("error"),
                error_details=result.get("error_details"),
            )

        # Success: Convert BuildingInfo to BuildingInfoResponse
        building_data = result["building"]
        building_response = BuildingInfoResponse(
            building_id=building_data.building_id,
            gml_id=building_data.gml_id,
            latitude=building_data.latitude,
            longitude=building_data.longitude,
            distance_meters=building_data.distance_meters,
            height=building_data.height,
            usage=building_data.usage,
            measured_height=building_data.measured_height,
            name=building_data.name,
            relevance_score=building_data.relevance_score,
            name_similarity=building_data.name_similarity,
            match_reason=building_data.match_reason,
            has_lod2=building_data.has_lod2,
            has_lod3=building_data.has_lod3,
        )

        return PlateauBuildingIdSearchResponse(
            success=True,
            building=building_response,
            municipality_code=None,  # Not extracted in mesh-based search
            municipality_name=None,
            citygml_file=None,
            total_buildings_in_file=result["total_buildings_in_mesh"],
            error=None,
            error_details=None,
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        return PlateauBuildingIdSearchResponse(
            success=False,
            building=None,
            error="Internal server error",
            error_details=f"予期しないエラー: {str(e)}",
        )


# --- PLATEAU: Batch Building Search (Phase 6.1) ---
@router.post(
    "/api/plateau/buildings/batch",
    summary="PLATEAU Batch Building Search by ID + Mesh (Optimized)",
    tags=["PLATEAU Integration"],
    response_model=PlateauBatchBuildingResponse,
    responses={
        200: {
            "description": "Batch search results for multiple buildings",
            "content": {
                "application/json": {
                    "example": {
                        "results": [
                            {
                                "success": True,
                                "building": {
                                    "building_id": "13101-bldg-2287",
                                    "gml_id": "bldg_48aa415d-b82f-4e8f-97e1-7538b5cb6c86",
                                    "latitude": 35.681236,
                                    "longitude": 139.767125,
                                    "height": 45.0,
                                },
                            }
                        ],
                        "total_requested": 2,
                        "total_success": 1,
                        "total_failed": 1,
                    }
                }
            },
        },
        400: {"description": "Invalid request (empty list or > 100 buildings)"},
        500: {"description": "Internal server error"},
    },
)
async def plateau_batch_search_buildings(request: PlateauBatchBuildingRequest):
    """
    複数の建物を一括検索（建物ID+メッシュコード）。

    Batch search for multiple PLATEAU buildings by building ID + mesh code (optimized).

    **最適化 / Optimization**:
    - ✅ メッシュコードでグループ化して処理 / Group by mesh code to minimize file downloads
    - ✅ 同じメッシュ内の建物は1回のダウンロードで処理 / Buildings in same mesh use single download
    - ⚡ N+1クエリ問題を解消 / Eliminates N+1 query problem

    **制限 / Limits**:
    - 最大100建物/リクエスト / Max 100 buildings per request
    - レート制限: PLATEAU API制限に準拠 / Rate limit: Follows PLATEAU API limits

    **入力例 / Example Input**:
    ```json
    {
        "buildings": [
            {"building_id": "bldg_48aa415d-b82f-4e8f-97e1-7538b5cb6c86", "mesh_code": "53394511"},
            {"building_id": "bldg_12345678-1234-1234-1234-123456789abc", "mesh_code": "53394512"}
        ]
    }
    ```

    **用途 / Use Cases**:
    - Cesium選択パネルでの複数建物メタデータ取得 / Multi-select metadata fetch in Cesium picker
    - 大量建物の一括処理 / Batch processing of many buildings
    """
    try:
        print(f"\n{'=' * 60}")
        print(f"[API] /api/plateau/buildings/batch")
        print(f"[API] Total buildings requested: {len(request.buildings)}")
        print(f"{'=' * 60}\n")

        results = []
        total_requested = len(request.buildings)
        total_success = 0
        total_failed = 0

        # Group by mesh code to minimize file downloads
        mesh_groups: dict[str, list[str]] = {}
        for item in request.buildings:
            if item.mesh_code not in mesh_groups:
                mesh_groups[item.mesh_code] = []
            mesh_groups[item.mesh_code].append(item.building_id)

        print(f"[API] Grouped into {len(mesh_groups)} mesh code(s)")

        loop = asyncio.get_event_loop()

        # Process each mesh group
        for mesh_code, building_ids in mesh_groups.items():
            print(f"[API] Processing mesh {mesh_code}: {len(building_ids)} buildings")

            for building_id in building_ids:
                try:
                    # Search for building
                    result = await loop.run_in_executor(
                        None,
                        partial(
                            search_building_by_id_and_mesh,
                            building_id,
                            mesh_code,
                            debug=False,
                        ),
                    )

                    if result["success"]:
                        # Success: Convert to response
                        building_data = result["building"]
                        building_response = BuildingInfoResponse(
                            building_id=building_data.building_id,
                            gml_id=building_data.gml_id,
                            latitude=building_data.latitude,
                            longitude=building_data.longitude,
                            distance_meters=building_data.distance_meters,
                            height=building_data.height,
                            usage=building_data.usage,
                            measured_height=building_data.measured_height,
                            name=building_data.name,
                            relevance_score=building_data.relevance_score,
                            name_similarity=building_data.name_similarity,
                            match_reason=building_data.match_reason,
                            has_lod2=building_data.has_lod2,
                            has_lod3=building_data.has_lod3,
                        )

                        results.append(
                            PlateauBuildingIdSearchResponse(
                                success=True,
                                building=building_response,
                                municipality_code=None,
                                municipality_name=None,
                                citygml_file=None,
                                total_buildings_in_file=result.get(
                                    "total_buildings_in_mesh"
                                ),
                                error=None,
                                error_details=None,
                            )
                        )
                        total_success += 1

                    else:
                        # Failure: Add error response
                        results.append(
                            PlateauBuildingIdSearchResponse(
                                success=False,
                                building=None,
                                municipality_code=None,
                                municipality_name=None,
                                citygml_file=None,
                                total_buildings_in_file=result.get(
                                    "total_buildings_in_mesh"
                                ),
                                error=result.get("error", "Unknown error"),
                                error_details=result.get("error_details"),
                            )
                        )
                        total_failed += 1

                except Exception as e:
                    print(f"[API] Error fetching building {building_id}: {str(e)}")
                    results.append(
                        PlateauBuildingIdSearchResponse(
                            success=False,
                            building=None,
                            municipality_code=None,
                            municipality_name=None,
                            citygml_file=None,
                            total_buildings_in_file=None,
                            error="Internal error",
                            error_details=f"予期しないエラー: {str(e)}",
                        )
                    )
                    total_failed += 1

        print(f"[API] Batch complete: {total_success} success, {total_failed} failed")

        return PlateauBatchBuildingResponse(
            results=results,
            total_requested=total_requested,
            total_success=total_success,
            total_failed=total_failed,
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"バッチ検索エラー: {str(e)}")


@router.post(
    "/api/plateau/fetch-by-id-and-mesh",
    summary="PLATEAU Fetch & Convert by ID + Mesh (Optimized)",
    tags=["PLATEAU Integration"],
    responses={
        200: {
            "description": "STEP file from 1km² mesh area (fast)",
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"},
                    "example": "STEP file from mesh 53394511",
                }
            },
        },
        400: {"description": "Invalid mesh code format"},
        404: {"description": "Building not found in mesh"},
        500: {"description": "PLATEAU API or conversion error"},
    },
)
async def plateau_fetch_by_id_and_mesh(request: PlateauBuildingIdWithMeshRequest):
    """
    建物ID＋メッシュコードでSTEP変換（最適化版、高速）。

    Fetch PLATEAU building by GML ID + mesh code and convert to STEP format (optimized, fast).

    **最適化 / Optimization**:
    - ✅ 1km²のメッシュのみダウンロード / Download only 1km² mesh area
    - ⚡ `/api/plateau/fetch-by-id`より大幅に高速 / Much faster than /fetch-by-id
    - 💾 データ転送量が大幅削減 / Significantly reduced data transfer

    **入力例 / Example Input**:
    ```json
    {
        "building_id": "bldg_48aa415d-b82f-4e8f-97e1-7538b5cb6c86",
        "mesh_code": "53394511",
        "precision_mode": "ultra",
        "shape_fix_level": "minimal"
    }
    ```
    """
    if not OCCT_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="OpenCASCADE が利用できません。STEPファイルの変換には OpenCASCADE が必要です。",
        )

    try:
        print(f"\n{'=' * 60}")
        print(f"[API] /api/plateau/fetch-by-id-and-mesh")
        print(f"[API] Building ID: {request.building_id}")
        print(f"[API] Mesh Code: {request.mesh_code}")
        print(f"[API] Precision Mode: {request.precision_mode}")
        print(f"[API] Shape Fix Level: {request.shape_fix_level}")
        print(f"{'=' * 60}\n")

        # Step 1: Search for building by ID + mesh code
        loop = asyncio.get_event_loop()
        search_result = await loop.run_in_executor(
            None,
            partial(
                search_building_by_id_and_mesh,
                request.building_id,
                request.mesh_code,
                debug=request.debug,
            ),
        )

        if not search_result["success"]:
            error_msg = search_result.get("error", "Building not found")
            error_details = search_result.get("error_details", "")
            raise HTTPException(status_code=404, detail=f"{error_msg}. {error_details}")

        # Step 2: Convert to STEP
        citygml_xml = search_result.get("citygml_xml")
        if not citygml_xml:
            raise HTTPException(
                status_code=500, detail="CityGML data is missing from search result"
            )

        # Save CityGML to temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".gml", delete=False, encoding="utf-8"
        ) as tmp_gml:
            tmp_gml.write(citygml_xml)
            tmp_gml_path = tmp_gml.name

        # Create temporary STEP output file
        step_file_name = f"{request.building_id.replace('-', '_')}.step"
        tmp_step_path = os.path.join(tempfile.gettempdir(), step_file_name)

        try:
            # Export to STEP with specified building ID filter
            success, message = await loop.run_in_executor(
                None,
                partial(
                    export_step_from_citygml,
                    tmp_gml_path,
                    tmp_step_path,
                    building_ids=[request.building_id],
                    filter_attribute="gml:id",
                    method=request.method,
                    auto_reproject=request.auto_reproject,
                    precision_mode=request.precision_mode,
                    shape_fix_level=request.shape_fix_level,
                    merge_building_parts=request.merge_building_parts,
                    debug=request.debug,
                ),
            )

            if not success:
                raise HTTPException(
                    status_code=500,
                    detail=f"CityGML to STEP conversion failed: {message}",
                )

            # Verify STEP file exists
            if not os.path.exists(tmp_step_path):
                raise HTTPException(status_code=500, detail="STEP file was not created")

            # Return STEP file
            print(
                f"[API] Success: Returning STEP file for building {request.building_id}"
            )
            return FileResponse(
                path=tmp_step_path,
                media_type="application/octet-stream",
                filename=step_file_name,
                background=BackgroundTasks(),
            )

        finally:
            # Clean up temporary CityGML file
            if os.path.exists(tmp_gml_path):
                os.remove(tmp_gml_path)

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"予期しないエラー: {str(e)}")


@router.post(
    "/api/plateau/unfold-textured-by-id-and-mesh",
    summary="PLATEAU Textured Unfold by ID + Mesh (Beta)",
    tags=["PLATEAU Integration"],
    responses={
        200: {
            "description": "JSON response with textured SVG unfold result",
            "content": {
                "application/json": {
                    "example": {
                        "svg_content": "<svg>...</svg>",
                        "face_numbers": [{"faceIndex": 0, "faceNumber": 1}],
                        "texture_mappings": [
                            {
                                "faceNumber": 1,
                                "patternId": "plateau_deadbeef",
                                "tileCount": 1,
                                "rotation": 0,
                            }
                        ],
                        "stats": {"page_count": 1},
                    }
                }
            },
        },
        404: {"description": "Building not found in specified mesh"},
        500: {"description": "Conversion or textured unfold generation error"},
    },
)
async def plateau_unfold_textured_by_id_and_mesh(request: PlateauTexturedUnfoldRequest):
    """
    建物ID＋メッシュコードから、建物テクスチャ付き展開図を生成（ベータ）。

    Pipeline:
    1. Search target building in 1km mesh
    2. Convert the target building from CityGML to STEP
    3. Extract ParameterizedTexture from CityGML and map to STEP faces
    4. Generate unfold SVG (JSON response) using existing StepUnfold pipeline
    """
    if not OCCT_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="OpenCASCADE が利用できません。展開図生成には OpenCASCADE が必要です。",
        )

    tmp_gml_path = None
    tmp_step_path = None
    output_tmpdir = None

    try:
        print(f"\n{'=' * 60}")
        print(f"[API] /api/plateau/unfold-textured-by-id-and-mesh")
        print(f"[API] Building ID: {request.building_id}")
        print(f"[API] Mesh Code: {request.mesh_code}")
        print(
            f"[API] Layout: {request.layout_mode}, Page: {request.page_format}/{request.page_orientation}"
        )
        print(f"{'=' * 60}\n")

        # Step 1: Search building by ID + mesh code
        loop = asyncio.get_event_loop()
        search_result = await loop.run_in_executor(
            None,
            partial(
                search_building_by_id_and_mesh,
                request.building_id,
                request.mesh_code,
                debug=request.debug or False,
            ),
        )
        if not search_result["success"]:
            error_msg = search_result.get("error", "Building not found")
            error_details = search_result.get("error_details", "")
            raise HTTPException(status_code=404, detail=f"{error_msg}. {error_details}")

        citygml_xml = search_result.get("citygml_xml")
        if not citygml_xml:
            raise HTTPException(
                status_code=500, detail="CityGML data is missing from search result"
            )

        # Use resolved gml:id from search result to ensure filtering correctness.
        building_data = search_result.get("building")
        target_gml_id = building_data.gml_id if building_data else request.building_id
        source_urls = search_result.get("citygml_source_urls") or []

        # Step 2: CityGML -> STEP (target building only)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".gml", delete=False, encoding="utf-8"
        ) as tmp_gml:
            tmp_gml.write(citygml_xml)
            tmp_gml_path = tmp_gml.name

        tmp_step_path = os.path.join(
            tempfile.gettempdir(), f"plateau_textured_unfold_{uuid.uuid4()}.step"
        )

        success, message = await loop.run_in_executor(
            None,
            partial(
                export_step_from_citygml,
                tmp_gml_path,
                tmp_step_path,
                building_ids=[target_gml_id],
                filter_attribute="gml:id",
                method=request.method or "solid",
                auto_reproject=request.auto_reproject
                if request.auto_reproject is not None
                else True,
                precision_mode=request.precision_mode or "ultra",
                shape_fix_level=request.shape_fix_level or "minimal",
                merge_building_parts=request.merge_building_parts or False,
                debug=request.debug or False,
            ),
        )
        if not success:
            raise HTTPException(
                status_code=500, detail=f"CityGML to STEP conversion failed: {message}"
            )
        if not os.path.exists(tmp_step_path):
            raise HTTPException(status_code=500, detail="STEP file was not created")

        # Step 3: Analyze STEP faces and build texture mappings from CityGML appearance
        generator = StepUnfoldGenerator()
        load_ok = await loop.run_in_executor(
            None, partial(generator.load_from_file, tmp_step_path)
        )
        if not load_ok:
            raise HTTPException(
                status_code=500, detail="Generated STEP file could not be loaded"
            )

        await loop.run_in_executor(None, generator.analyze_brep_topology)
        texture_result = await loop.run_in_executor(
            None,
            partial(
                build_plateau_texture_mappings,
                citygml_xml=citygml_xml,
                building_gml_id=target_gml_id,
                step_faces_data=generator.faces_data,
                source_urls=source_urls,
                auto_reproject=request.auto_reproject
                if request.auto_reproject is not None
                else True,
            ),
        )
        texture_mappings = texture_result.get("texture_mappings") or []
        if texture_mappings:
            generator.set_texture_mappings(texture_mappings)
            print(f"[API] Applied {len(texture_mappings)} texture mappings")
        else:
            print(
                "[API] No texture mappings generated; fallback to non-textured unfold"
            )

        # Step 4: Generate unfold SVG as JSON response
        unfold_request = BrepPapercraftRequest(
            layout_mode=request.layout_mode or "paged",
            page_format=request.page_format or "A4",
            page_orientation=request.page_orientation or "portrait",
            scale_factor=request.scale_factor or 10.0,
            mirror_horizontal=request.mirror_horizontal or False,
            max_faces=request.max_faces or 20,
        )

        output_tmpdir = tempfile.mkdtemp()
        svg_path = os.path.join(
            output_tmpdir, f"plateau_textured_unfold_{uuid.uuid4()}.svg"
        )
        generated_svg_path, stats = await loop.run_in_executor(
            None,
            partial(generator.generate_brep_papercraft, unfold_request, svg_path),
        )

        with open(generated_svg_path, "r", encoding="utf-8") as f:
            svg_content = f.read()

        response_data: Dict[str, Any] = {
            "svg_content": svg_content,
            "stats": stats,
            "texture_mappings": texture_mappings,
            "texture_stats": texture_result.get("stats", {}),
            "building": {
                "gml_id": target_gml_id,
                "mesh_code": request.mesh_code,
            },
        }

        if request.return_face_numbers:
            response_data["face_numbers"] = generator.get_face_numbers()

        combined_warnings = []
        combined_warnings.extend(texture_result.get("warnings") or [])
        if stats.get("warnings"):
            combined_warnings.extend(stats.get("warnings"))
        if combined_warnings:
            response_data["warnings"] = combined_warnings

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"予期しないエラー: {str(e)}")
    finally:
        import shutil

        if tmp_gml_path and os.path.exists(tmp_gml_path):
            os.remove(tmp_gml_path)
        if tmp_step_path and os.path.exists(tmp_step_path):
            os.remove(tmp_step_path)
        if output_tmpdir and os.path.exists(output_tmpdir):
            shutil.rmtree(output_tmpdir, ignore_errors=True)


# --- PLATEAU Mesh to 3D Tiles Converter ---
@router.post(
    "/api/plateau/mesh-to-tilesets",
    summary="Convert Mesh Codes to 3D Tiles URLs",
    tags=["PLATEAU Integration"],
    response_model=MeshToTilesetsResponse,
    responses={
        200: {
            "description": "3D Tiles URLs for requested mesh codes",
            "content": {
                "application/json": {
                    "example": {
                        "tilesets": [
                            {
                                "mesh_code": "53394511",
                                "tileset_url": "https://assets.cms.plateau.reearth.io/assets/.../tileset.json",
                                "municipality_name": "千代田区",
                                "municipality_code": "13101",
                            }
                        ],
                        "total_requested": 9,
                        "total_found": 1,
                        "total_not_found": 8,
                    }
                }
            },
        }
    },
)
async def mesh_to_tilesets(request: MeshToTilesetsRequest) -> MeshToTilesetsResponse:
    """
    メッシュコードのリスト → 3D Tiles URLのリストに変換

    PLATEAU Data Catalog APIを使用して、各メッシュコードに対応する
    3D Tiles tilesetのURLを取得します。

    **Implementation Note:**
    事前生成した mesh2→自治体マップ（N03ベース）を使用します。
    ランタイムは JSON を読むだけで全国対応します。

    ### リクエスト例
    ```json
    {
        "mesh_codes": ["53394511", "53394512", "53394521"],
        "lod": 1
    }
    ```

    ### レスポンス例
    ```json
    {
        "tilesets": [
            {
                "mesh_code": "53394511",
                "tileset_url": "https://assets.cms.plateau.reearth.io/assets/.../tileset.json",
                "municipality_name": "千代田区",
                "municipality_code": "13101"
            }
        ],
        "total_requested": 9,
        "total_found": 1,
        "total_not_found": 8
    }
    ```

    ### メッシュコードについて
    - 3次メッシュコード（8桁）を使用
    - 1メッシュ = 約1km x 1km
    - 周辺メッシュを含めて検索することで境界付近の建物もカバー

    ### 制限事項
    - 最大25メッシュまで（5x5グリッド）
    - 同じ市区町村の重複したURLは除外されます
    """
    try:
        print(f"\n{'=' * 60}")
        print(f"[API] /api/plateau/mesh-to-tilesets")
        print(f"[API] Mesh Codes: {request.mesh_codes}")
        print(f"[API] LOD: {request.lod}")
        print(f"[API] Prefer no texture: {request.prefer_no_texture}")
        print(f"{'=' * 60}\n")

        if request.municipality_code:
            dataset = await fetch_plateau_dataset_by_municipality(
                request.municipality_code,
                request.lod,
                request.prefer_no_texture,
            )
            if dataset:
                mesh_code = (
                    request.mesh_codes[0]
                    if request.mesh_codes
                    else request.municipality_code
                )
                tilesets = [
                    TilesetInfo(
                        mesh_code=mesh_code,
                        tileset_url=dataset["tileset_url"],
                        municipality_name=dataset.get("municipality_name"),
                        municipality_code=request.municipality_code,
                    )
                ]
                total_requested = len(request.mesh_codes)
                total_found = len(tilesets)
                total_not_found = total_requested - total_found

                print(
                    f"[API] Using municipality filter {request.municipality_code}: "
                    f"Found {total_found}/{total_requested} tilesets"
                )

                return MeshToTilesetsResponse(
                    tilesets=tilesets,
                    total_requested=total_requested,
                    total_found=total_found,
                    total_not_found=total_not_found,
                )

            print(
                f"[API] Municipality {request.municipality_code} not found for LOD{request.lod}, "
                "falling back to mesh lookup"
            )

        # Fetch 3D Tiles URLs for mesh codes
        tilesets_data = await fetch_tilesets_for_meshes(
            request.mesh_codes,
            request.lod,
            request.prefer_no_texture,
        )

        # Build response
        tilesets = [
            TilesetInfo(
                mesh_code=data["mesh_code"],
                tileset_url=data["tileset_url"],
                municipality_name=data.get("municipality_name"),
                municipality_code=data.get("municipality_code"),
            )
            for data in tilesets_data
        ]

        total_requested = len(request.mesh_codes)
        total_found = len(tilesets)
        total_not_found = total_requested - total_found

        print(f"[API] Found {total_found}/{total_requested} tilesets")

        return MeshToTilesetsResponse(
            tilesets=tilesets,
            total_requested=total_requested,
            total_found=total_found,
            total_not_found=total_not_found,
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"予期しないエラー: {str(e)}")
