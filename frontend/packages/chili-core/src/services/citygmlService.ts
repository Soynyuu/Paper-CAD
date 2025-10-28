// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { IApplication } from "../application";
import { Result } from "../foundation";
import { IService } from "../service";

export interface CityGMLConversionOptions {
    defaultHeight?: number;
    limit?: number;
    debug?: boolean;
    method?: "auto" | "solid" | "sew" | "extrude";
    sewTolerance?: number;
    reprojectTo?: string;
    sourceCrs?: string;
    autoReproject?: boolean;
    buildingIds?: string[];
    filterAttribute?: string;
}

export interface ICityGMLService extends IService {
    convertToStep(cityGmlFile: File, options?: CityGMLConversionOptions): Promise<Result<Blob>>;
    validateCityGML(cityGmlFile: File): Promise<Result<ValidationResponse>>;
    searchByAddress(query: string, options?: PlateauSearchOptions): Promise<Result<PlateauSearchResponse>>;
    fetchAndConvertByAddress(query: string, options?: PlateauFetchAndConvertOptions): Promise<Result<Blob>>;
    searchByBuildingId(
        buildingId: string,
        options?: PlateauBuildingIdSearchOptions,
    ): Promise<Result<PlateauBuildingIdSearchResponse>>;
    searchByBuildingIdAndMesh(
        buildingId: string,
        meshCode: string,
        options?: PlateauBuildingIdWithMeshSearchOptions,
    ): Promise<Result<PlateauBuildingIdSearchResponse>>;
}

export interface ValidationResponse {
    valid: boolean;
    buildings_with_footprints: number;
    sample_building_id?: string;
    notes: string;
}

export interface BuildingInfo {
    building_id?: string;
    gml_id: string;
    latitude: number;
    longitude: number;
    distance_meters: number;
    height?: number;
    usage?: string;
    measured_height?: number;
    building_structure_type?: string;
    has_lod2?: boolean;
    has_lod3?: boolean;
    name?: string;
    relevance_score?: number;
    name_similarity?: number;
    match_reason?: string;
}

export interface GeocodingResult {
    query: string;
    latitude: number;
    longitude: number;
    display_name: string;
    osm_type?: string;
    osm_id?: number;
}

export interface PlateauSearchResponse {
    success: boolean;
    geocoding?: GeocodingResult;
    buildings: BuildingInfo[];
    found_count: number;
    search_mode?: string;
    error?: string;
}

export interface PlateauSearchOptions {
    radius?: number; // Search radius in degrees (default: 0.001 ≈ 100m)
    limit?: number; // Maximum number of buildings to return
    nameFilter?: string; // Building name to filter/rank by
    searchMode?: "distance" | "name" | "hybrid"; // Search ranking strategy
}

export interface PlateauFetchAndConvertOptions extends PlateauSearchOptions {
    buildingLimit?: number; // Number of buildings to convert
    buildingIds?: string[]; // Specific building IDs to convert (gml:id format)
    debug?: boolean;
    method?: "auto" | "solid" | "sew" | "extrude";
    autoReproject?: boolean;
    mergeBuildingParts?: boolean; // Merge BuildingParts into single solid (default: false, preserves detail)
}

export interface PlateauBuildingIdSearchOptions {
    debug?: boolean;
}

export interface PlateauBuildingIdWithMeshSearchOptions {
    debug?: boolean;
    mergeBuildingParts?: boolean;
}

export interface PlateauBuildingIdSearchResponse {
    success: boolean;
    building?: BuildingInfo;
    municipality_code?: string;
    municipality_name?: string;
    citygml_file?: string;
    total_buildings_in_file?: number;
    error?: string;
    error_details?: string;
}

export class CityGMLService implements ICityGMLService {
    private readonly baseUrl: string;

    constructor(baseUrl: string = "http://localhost:8001/api") {
        this.baseUrl = baseUrl;
    }

    register(_app: IApplication): void {
        // Service registration
    }

    start(): void {
        // Service start
    }

    stop(): void {
        // Service stop
    }

    async convertToStep(cityGmlFile: File, options?: CityGMLConversionOptions): Promise<Result<Blob>> {
        try {
            // Validate file extension
            if (!this.isValidCityGMLFile(cityGmlFile)) {
                return Result.err("Invalid CityGML file. Please select a .gml or .xml file.");
            }

            const formData = new FormData();
            formData.append("file", cityGmlFile);

            // Add optional parameters
            if (options?.defaultHeight !== undefined) {
                formData.append("default_height", options.defaultHeight.toString());
            }
            if (options?.limit !== undefined) {
                formData.append("limit", options.limit.toString());
            }
            if (options?.debug !== undefined) {
                formData.append("debug", options.debug.toString());
            }
            if (options?.method) {
                formData.append("method", options.method);
            }
            if (options?.sewTolerance !== undefined) {
                formData.append("sew_tolerance", options.sewTolerance.toString());
            }
            if (options?.reprojectTo) {
                formData.append("reproject_to", options.reprojectTo);
            }
            if (options?.sourceCrs) {
                formData.append("source_crs", options.sourceCrs);
            }
            if (options?.autoReproject !== undefined) {
                formData.append("auto_reproject", options.autoReproject.toString());
            }
            if (options?.buildingIds && options.buildingIds.length > 0) {
                formData.append("building_ids", options.buildingIds.join(","));
            }
            if (options?.filterAttribute) {
                formData.append("filter_attribute", options.filterAttribute);
            }

            const response = await fetch(`${this.baseUrl}/citygml/to-step`, {
                method: "POST",
                body: formData,
            });

            if (!response.ok) {
                let errorMessage: string;
                if (response.status === 400) {
                    const errorData = await response.json().catch(() => null);
                    errorMessage =
                        errorData?.detail || "CityGML file conversion failed. Please check the file format.";
                } else if (response.status === 413) {
                    errorMessage =
                        "File size too large. Please use a smaller file or limit the number of buildings.";
                } else if (response.status === 503) {
                    errorMessage =
                        "Backend service unavailable. Please ensure the conversion service is running.";
                } else {
                    errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                }
                return Result.err(errorMessage);
            }

            // Get the response as blob
            const blob = await response.blob();
            return Result.ok(blob);
        } catch (error) {
            if (error instanceof Error) {
                // Check for network errors
                if (error.message.includes("fetch")) {
                    return Result.err(
                        "Cannot connect to CityGML conversion service. Please ensure the backend is running on " +
                            this.baseUrl,
                    );
                }
                return Result.err(error.message);
            }
            return Result.err("Unknown error during CityGML conversion");
        }
    }

    async validateCityGML(cityGmlFile: File): Promise<Result<ValidationResponse>> {
        try {
            if (!this.isValidCityGMLFile(cityGmlFile)) {
                return Result.err("Invalid CityGML file. Please select a .gml or .xml file.");
            }

            const formData = new FormData();
            formData.append("file", cityGmlFile);
            formData.append("limit", "10");

            const response = await fetch(`${this.baseUrl}/citygml/validate`, {
                method: "POST",
                body: formData,
            });

            if (!response.ok) {
                return Result.err(`Validation failed: ${response.status} ${response.statusText}`);
            }

            const validationData = await response.json();
            return Result.ok(validationData);
        } catch (error) {
            return Result.err(error instanceof Error ? error.message : "Unknown validation error");
        }
    }

    async searchByAddress(
        query: string,
        options?: PlateauSearchOptions,
    ): Promise<Result<PlateauSearchResponse>> {
        try {
            const requestBody = {
                query,
                radius: options?.radius ?? 0.001,
                limit: options?.limit ?? 10,
                auto_select_nearest: true,
                name_filter: options?.nameFilter,
                search_mode: options?.searchMode ?? "hybrid",
            };

            const response = await fetch(`${this.baseUrl}/plateau/search-by-address`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(requestBody),
            });

            if (!response.ok) {
                let errorMessage: string;
                if (response.status === 404) {
                    errorMessage = "Address or buildings not found";
                } else if (response.status === 500) {
                    const errorData = await response.json().catch(() => null);
                    errorMessage = errorData?.detail || "Search failed due to server error";
                } else {
                    errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                }
                return Result.err(errorMessage);
            }

            const data: PlateauSearchResponse = await response.json();
            return Result.ok(data);
        } catch (error) {
            if (error instanceof Error) {
                if (error.message.includes("fetch")) {
                    return Result.err(
                        "Cannot connect to PLATEAU search service. Please ensure the backend is running on " +
                            this.baseUrl,
                    );
                }
                return Result.err(error.message);
            }
            return Result.err("Unknown error during PLATEAU address search");
        }
    }

    async fetchAndConvertByAddress(
        query: string,
        options?: PlateauFetchAndConvertOptions,
    ): Promise<Result<Blob>> {
        try {
            const formData = new FormData();
            formData.append("query", query);

            if (options?.radius !== undefined) {
                formData.append("radius", options.radius.toString());
            }
            if (options?.buildingLimit !== undefined) {
                formData.append("building_limit", options.buildingLimit.toString());
            }
            if (options?.buildingIds && options.buildingIds.length > 0) {
                formData.append("building_ids", options.buildingIds.join(","));
            }
            if (options?.debug !== undefined) {
                formData.append("debug", options.debug.toString());
            }
            if (options?.method) {
                formData.append("method", options.method);
            }
            if (options?.autoReproject !== undefined) {
                formData.append("auto_reproject", options.autoReproject.toString());
            }
            if (options?.mergeBuildingParts !== undefined) {
                formData.append("merge_building_parts", options.mergeBuildingParts.toString());
            }

            const response = await fetch(`${this.baseUrl}/plateau/fetch-and-convert`, {
                method: "POST",
                body: formData,
            });

            if (!response.ok) {
                let errorMessage: string;
                if (response.status === 404) {
                    errorMessage = "No buildings found at the specified location";
                } else if (response.status === 400) {
                    const errorData = await response.json().catch(() => null);
                    errorMessage = errorData?.detail || "Invalid request parameters";
                } else if (response.status === 500) {
                    const errorData = await response.json().catch(() => null);
                    errorMessage = errorData?.detail || "Conversion failed due to server error";
                } else {
                    errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                }
                return Result.err(errorMessage);
            }

            const blob = await response.blob();
            return Result.ok(blob);
        } catch (error) {
            if (error instanceof Error) {
                if (error.message.includes("fetch")) {
                    return Result.err(
                        "Cannot connect to PLATEAU conversion service. Please ensure the backend is running on " +
                            this.baseUrl,
                    );
                }
                return Result.err(error.message);
            }
            return Result.err("Unknown error during PLATEAU fetch and convert");
        }
    }

    async searchByBuildingId(
        buildingId: string,
        options?: PlateauBuildingIdSearchOptions,
    ): Promise<Result<PlateauBuildingIdSearchResponse>> {
        try {
            const requestBody = {
                building_id: buildingId,
                debug: options?.debug ?? false,
            };

            const response = await fetch(`${this.baseUrl}/plateau/search-by-id`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(requestBody),
            });

            if (!response.ok) {
                let errorMessage: string;
                if (response.status === 404) {
                    const errorData = await response.json().catch(() => null);
                    errorMessage = errorData?.error_details || "Building not found";
                } else if (response.status === 400) {
                    const errorData = await response.json().catch(() => null);
                    errorMessage = errorData?.error_details || "Invalid building ID format";
                } else if (response.status === 500) {
                    const errorData = await response.json().catch(() => null);
                    errorMessage = errorData?.error_details || "Search failed due to server error";
                } else {
                    errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                }
                return Result.err(errorMessage);
            }

            const data: PlateauBuildingIdSearchResponse = await response.json();
            return Result.ok(data);
        } catch (error) {
            if (error instanceof Error) {
                if (error.message.includes("fetch")) {
                    return Result.err(
                        "Cannot connect to PLATEAU building ID search service. Please ensure the backend is running on " +
                            this.baseUrl,
                    );
                }
                return Result.err(error.message);
            }
            return Result.err("Unknown error during PLATEAU building ID search");
        }
    }

    async searchByBuildingIdAndMesh(
        buildingId: string,
        meshCode: string,
        options?: PlateauBuildingIdWithMeshSearchOptions,
    ): Promise<Result<PlateauBuildingIdSearchResponse>> {
        try {
            const requestBody = {
                building_id: buildingId,
                mesh_code: meshCode,
                debug: options?.debug ?? false,
                merge_building_parts: options?.mergeBuildingParts ?? false,
            };

            const response = await fetch(`${this.baseUrl}/plateau/search-by-id-and-mesh`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(requestBody),
            });

            if (!response.ok) {
                let errorMessage: string;
                if (response.status === 404) {
                    const errorData = await response.json().catch(() => null);
                    errorMessage = errorData?.error_details || "Building not found in mesh area";
                } else if (response.status === 400) {
                    const errorData = await response.json().catch(() => null);
                    errorMessage = errorData?.error_details || "Invalid building ID or mesh code format";
                } else if (response.status === 500) {
                    const errorData = await response.json().catch(() => null);
                    errorMessage = errorData?.error_details || "Search failed due to server error";
                } else {
                    errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                }
                return Result.err(errorMessage);
            }

            const data: PlateauBuildingIdSearchResponse = await response.json();
            return Result.ok(data);
        } catch (error) {
            if (error instanceof Error) {
                if (error.message.includes("fetch")) {
                    return Result.err(
                        "Cannot connect to PLATEAU building ID + mesh code search service. Please ensure the backend is running on " +
                            this.baseUrl,
                    );
                }
                return Result.err(error.message);
            }
            return Result.err("Unknown error during PLATEAU building ID + mesh code search");
        }
    }

    private isValidCityGMLFile(file: File): boolean {
        const validExtensions = [".gml", ".xml"];
        const fileName = file.name.toLowerCase();
        return validExtensions.some((ext) => fileName.endsWith(ext));
    }
}
