export interface Region {
  id: string;
  name: string;
  prefecture: string;
  center: {
    lat: number;
    lng: number;
  };
  zoom: number;
}

export interface DataType {
  id: string;
  name: string;
  description: string;
  fileIdentifier: string;
}

export interface LODLevel {
  level: string;
  description: string;
  estimatedSize: string;
}

export interface Building {
  id: string;
  gmlId: string;
  x: number;
  y: number;
  z: number;
  width: number;
  depth: number;
  height: number;
  area: number;
  volume: number;
  selected: boolean;
  position: {
    longitude: number;
    latitude: number;
    altitude: number;
  };
  metadata: {
    name?: string;
    address?: string;
    floors?: number;
    usage?: string;
    constructionYear?: number;
    measuredHeight?: number;
    roofType?: string;
    wallMaterial?: string;
  };
  lodData: {
    lod1?: string;
    lod2?: string;
    lod3?: string;
  };
}

export interface MapViewport {
  width: number;
  height: number;
  offsetX: number;
  offsetY: number;
  scale: number;
}

export interface DownloadOptions {
  region: string;
  dataTypes: string[];
  lodLevel: string;
  buildings: string[];
  format: 'citygml' | 'geojson' | 'shapefile' | '3dtiles';
  coordinateSystem: 'jgd2011' | 'wgs84';
  compression: boolean;
}

export interface PlateauDataset {
  id: string;
  title: string;
  description: string;
  prefecture: string;
  city: string;
  year: number;
  dataTypes: string[];
  boundingBox: {
    north: number;
    south: number;
    east: number;
    west: number;
  };
  tilesetUrl?: string;
  metadataUrl: string;
  downloadUrl: string;
  fileSize: number;
  lastUpdated: Date;
}

export interface User {
  id: string;
  email: string;
  name: string;
  organization?: string;
  role: 'free' | 'pro' | 'enterprise' | 'admin';
  apiKey?: string;
  usage: {
    downloads: number;
    bandwidth: number;
    apiCalls: number;
  };
  limits: {
    maxDownloadsPerMonth: number;
    maxBandwidthGB: number;
    maxApiCallsPerDay: number;
    maxBuildingsPerDownload: number;
  };
}