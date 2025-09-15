import axios from 'axios';
import { PlateauDataset, Building, DownloadOptions } from '@/types';

const PLATEAU_API_BASE = process.env.NEXT_PUBLIC_PLATEAU_API_BASE || 'https://www.geospatial.jp/ckan/api/3';
const PLATEAU_VIEW_BASE = 'https://plateauview.mlit.go.jp';

export class PlateauService {
  private static instance: PlateauService;
  private apiKey: string | undefined;
  
  private constructor() {
    this.apiKey = process.env.PLATEAU_API_KEY;
  }
  
  static getInstance(): PlateauService {
    if (!PlateauService.instance) {
      PlateauService.instance = new PlateauService();
    }
    return PlateauService.instance;
  }
  
  /**
   * Get available PLATEAU datasets for a region
   */
  async getDatasets(prefecture: string, city?: string): Promise<PlateauDataset[]> {
    try {
      const response = await axios.get(`${PLATEAU_API_BASE}/action/package_search`, {
        params: {
          q: `plateau ${prefecture} ${city || ''}`.trim(),
          rows: 100,
          sort: 'metadata_modified desc',
        },
      });
      
      return response.data.result.results.map((pkg: any) => this.mapToDataset(pkg));
    } catch (error) {
      console.error('Failed to fetch PLATEAU datasets:', error);
      throw new Error('Failed to fetch PLATEAU datasets');
    }
  }
  
  /**
   * Get 3D Tiles URL for a specific area
   */
  async get3DTilesUrl(datasetId: string): Promise<string | null> {
    try {
      const response = await axios.get(`${PLATEAU_API_BASE}/action/package_show`, {
        params: { id: datasetId },
      });
      
      const pkg = response.data.result;
      const tilesResource = pkg.resources.find((r: any) => 
        r.format?.toLowerCase() === '3dtiles' || 
        r.url?.includes('3dtiles')
      );
      
      if (tilesResource) {
        return tilesResource.url;
      }
      
      // Check for PLATEAU VIEW 3D Tiles
      const plateauViewUrl = await this.getPlateauView3DTiles(pkg);
      return plateauViewUrl;
    } catch (error) {
      console.error('Failed to get 3D Tiles URL:', error);
      return null;
    }
  }
  
  /**
   * Get PLATEAU VIEW 3D Tiles URL
   */
  private async getPlateauView3DTiles(dataset: any): Promise<string | null> {
    try {
      // Extract city code from dataset
      const cityCode = this.extractCityCode(dataset);
      if (!cityCode) return null;
      
      // PLATEAU VIEW 3D Tiles endpoints
      const endpoints = [
        `${PLATEAU_VIEW_BASE}/3dtiles/${cityCode}/tileset.json`,
        `${PLATEAU_VIEW_BASE}/data/${cityCode}/3dtiles/tileset.json`,
        `https://assets.cms.plateau.reearth.io/${cityCode}/tileset.json`,
      ];
      
      for (const url of endpoints) {
        try {
          const response = await axios.head(url);
          if (response.status === 200) {
            return url;
          }
        } catch {
          continue;
        }
      }
      
      return null;
    } catch (error) {
      console.error('Failed to get PLATEAU VIEW 3D Tiles:', error);
      return null;
    }
  }
  
  /**
   * Download CityGML data for selected buildings
   */
  async downloadCityGML(options: DownloadOptions): Promise<Blob> {
    const { region, buildings, dataTypes, lodLevel, format, coordinateSystem, compression } = options;
    
    try {
      // Get dataset for region
      const datasets = await this.getDatasets(region);
      if (datasets.length === 0) {
        throw new Error('No datasets available for this region');
      }
      
      const dataset = datasets[0];
      
      // Find CityGML resource
      const response = await axios.get(`${PLATEAU_API_BASE}/action/package_show`, {
        params: { id: dataset.id },
      });
      
      const citygmlResource = response.data.result.resources.find((r: any) => 
        r.format?.toLowerCase() === 'citygml' ||
        r.url?.includes('.gml') ||
        dataTypes.some(type => r.url?.includes(type))
      );
      
      if (!citygmlResource) {
        throw new Error('CityGML resource not found');
      }
      
      // Download and filter data
      const gmlResponse = await axios.get(citygmlResource.url, {
        responseType: 'blob',
        params: {
          buildings: buildings.join(','),
          lod: lodLevel,
          format,
          crs: coordinateSystem,
          compress: compression,
        },
      });
      
      return gmlResponse.data;
    } catch (error) {
      console.error('Failed to download CityGML:', error);
      throw new Error('Failed to download CityGML data');
    }
  }
  
  /**
   * Get building information by ID
   */
  async getBuildingInfo(buildingId: string, datasetId: string): Promise<Building | null> {
    try {
      // This would typically query a building database or parse CityGML
      // For now, return mock data
      return {
        id: buildingId,
        gmlId: buildingId,
        x: 0,
        y: 0,
        z: 0,
        width: Math.random() * 50 + 10,
        depth: Math.random() * 50 + 10,
        height: Math.random() * 100 + 10,
        area: Math.random() * 2000 + 100,
        volume: Math.random() * 50000 + 1000,
        selected: false,
        position: {
          longitude: 139.6917 + (Math.random() - 0.5) * 0.1,
          latitude: 35.6895 + (Math.random() - 0.5) * 0.1,
          altitude: 0,
        },
        metadata: {
          name: `Building ${buildingId}`,
          floors: Math.floor(Math.random() * 20) + 1,
          constructionYear: 1980 + Math.floor(Math.random() * 40),
          usage: ['residential', 'commercial', 'office', 'industrial'][Math.floor(Math.random() * 4)],
        },
        lodData: {},
      };
    } catch (error) {
      console.error('Failed to get building info:', error);
      return null;
    }
  }
  
  /**
   * Search buildings within bounding box
   */
  async searchBuildingsInBBox(
    bbox: { north: number; south: number; east: number; west: number },
    filters?: {
      minHeight?: number;
      maxHeight?: number;
      usage?: string[];
      yearFrom?: number;
      yearTo?: number;
    }
  ): Promise<Building[]> {
    try {
      // This would typically query a spatial database
      // For now, return mock data
      const buildings: Building[] = [];
      const count = Math.floor(Math.random() * 50) + 10;
      
      for (let i = 0; i < count; i++) {
        const building: Building = {
          id: `bldg-${i}`,
          gmlId: `bldg-${i}`,
          x: 0,
          y: 0,
          z: 0,
          width: Math.random() * 50 + 10,
          depth: Math.random() * 50 + 10,
          height: Math.random() * 150 + 10,
          area: Math.random() * 2000 + 100,
          volume: Math.random() * 50000 + 1000,
          selected: false,
          position: {
            longitude: bbox.west + Math.random() * (bbox.east - bbox.west),
            latitude: bbox.south + Math.random() * (bbox.north - bbox.south),
            altitude: 0,
          },
          metadata: {
            name: `Building ${i}`,
            floors: Math.floor(Math.random() * 20) + 1,
            constructionYear: 1980 + Math.floor(Math.random() * 40),
            usage: ['residential', 'commercial', 'office', 'industrial'][Math.floor(Math.random() * 4)],
          },
          lodData: {},
        };
        
        // Apply filters
        if (filters) {
          if (filters.minHeight && building.height < filters.minHeight) continue;
          if (filters.maxHeight && building.height > filters.maxHeight) continue;
          if (filters.usage && filters.usage.length > 0 && !filters.usage.includes(building.metadata.usage!)) continue;
          if (filters.yearFrom && building.metadata.constructionYear! < filters.yearFrom) continue;
          if (filters.yearTo && building.metadata.constructionYear! > filters.yearTo) continue;
        }
        
        buildings.push(building);
      }
      
      return buildings;
    } catch (error) {
      console.error('Failed to search buildings:', error);
      throw new Error('Failed to search buildings');
    }
  }
  
  /**
   * Get available data types for a dataset
   */
  async getAvailableDataTypes(datasetId: string): Promise<string[]> {
    try {
      const response = await axios.get(`${PLATEAU_API_BASE}/action/package_show`, {
        params: { id: datasetId },
      });
      
      const resources = response.data.result.resources;
      const dataTypes = new Set<string>();
      
      resources.forEach((resource: any) => {
        // Extract data type from URL or name
        const types = ['bldg', 'tran', 'luse', 'urf', 'frn', 'veg', 'wtr', 'dem', 'lsld', 'ubo'];
        types.forEach(type => {
          if (resource.url?.includes(type) || resource.name?.includes(type)) {
            dataTypes.add(type);
          }
        });
      });
      
      return Array.from(dataTypes);
    } catch (error) {
      console.error('Failed to get available data types:', error);
      return ['bldg']; // Default to buildings
    }
  }
  
  /**
   * Map API response to PlateauDataset
   */
  private mapToDataset(pkg: any): PlateauDataset {
    const bbox = this.extractBoundingBox(pkg);
    const location = this.extractLocation(pkg);
    
    return {
      id: pkg.id,
      title: pkg.title,
      description: pkg.notes || '',
      prefecture: location.prefecture,
      city: location.city,
      year: this.extractYear(pkg),
      dataTypes: this.extractDataTypes(pkg),
      boundingBox: bbox,
      metadataUrl: `${PLATEAU_API_BASE}/action/package_show?id=${pkg.id}`,
      downloadUrl: pkg.resources?.[0]?.url || '',
      fileSize: pkg.resources?.reduce((sum: number, r: any) => sum + (r.size || 0), 0) || 0,
      lastUpdated: new Date(pkg.metadata_modified),
    };
  }
  
  /**
   * Extract bounding box from package metadata
   */
  private extractBoundingBox(pkg: any): PlateauDataset['boundingBox'] {
    // Check for spatial extent in extras
    const spatial = pkg.extras?.find((e: any) => e.key === 'spatial')?.value;
    if (spatial) {
      try {
        const coords = JSON.parse(spatial);
        if (coords.type === 'Polygon' && coords.coordinates?.[0]) {
          const ring = coords.coordinates[0];
          return {
            west: Math.min(...ring.map((c: number[]) => c[0])),
            east: Math.max(...ring.map((c: number[]) => c[0])),
            south: Math.min(...ring.map((c: number[]) => c[1])),
            north: Math.max(...ring.map((c: number[]) => c[1])),
          };
        }
      } catch {}
    }
    
    // Default to Tokyo area
    return {
      north: 35.8,
      south: 35.5,
      east: 139.9,
      west: 139.5,
    };
  }
  
  /**
   * Extract location from package
   */
  private extractLocation(pkg: any): { prefecture: string; city: string } {
    const title = pkg.title || '';
    const tags = pkg.tags?.map((t: any) => t.name) || [];
    
    // Try to extract from title
    const prefectures = ['東京都', '大阪府', '愛知県', '神奈川県', '北海道', '福岡県', '宮城県'];
    const prefecture = prefectures.find(p => title.includes(p) || tags.includes(p)) || '';
    
    // Extract city
    const cityMatch = title.match(/（(.+?)）/) || title.match(/\[(.+?)\]/);
    const city = cityMatch?.[1] || '';
    
    return { prefecture, city };
  }
  
  /**
   * Extract year from package
   */
  private extractYear(pkg: any): number {
    const yearMatch = pkg.title?.match(/\d{4}/) || pkg.name?.match(/\d{4}/);
    return yearMatch ? parseInt(yearMatch[0]) : new Date().getFullYear();
  }
  
  /**
   * Extract data types from package
   */
  private extractDataTypes(pkg: any): string[] {
    const types = new Set<string>();
    const typeMap: Record<string, string> = {
      '建築物': 'bldg',
      '道路': 'tran',
      '土地利用': 'luse',
      '都市計画': 'urf',
      '都市設備': 'frn',
      '植生': 'veg',
      '水部': 'wtr',
      '地形': 'dem',
      '土砂災害': 'lsld',
      '地下埋設物': 'ubo',
    };
    
    // Check tags
    pkg.tags?.forEach((tag: any) => {
      Object.entries(typeMap).forEach(([key, value]) => {
        if (tag.name.includes(key)) {
          types.add(value);
        }
      });
    });
    
    // Check resources
    pkg.resources?.forEach((resource: any) => {
      Object.values(typeMap).forEach(type => {
        if (resource.url?.includes(type) || resource.name?.includes(type)) {
          types.add(type);
        }
      });
    });
    
    return Array.from(types);
  }
  
  /**
   * Extract city code from dataset
   */
  private extractCityCode(dataset: any): string | null {
    // Try to extract from name or tags
    const codeMatch = dataset.name?.match(/\d{5,6}/) || 
                      dataset.title?.match(/\d{5,6}/);
    return codeMatch?.[0] || null;
  }
}