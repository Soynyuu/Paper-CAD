import { Region, DataType, LODLevel } from '@/types';

export const REGIONS: Region[] = [
  {
    id: 'tokyo',
    name: '東京都',
    prefecture: '東京都',
    center: { lat: 35.6762, lng: 139.6503 },
    zoom: 10
  },
  {
    id: 'osaka',
    name: '大阪府',
    prefecture: '大阪府',
    center: { lat: 34.6937, lng: 135.5023 },
    zoom: 10
  },
  {
    id: 'nagoya',
    name: '名古屋市',
    prefecture: '愛知県',
    center: { lat: 35.1815, lng: 136.9066 },
    zoom: 11
  },
  {
    id: 'yokohama',
    name: '横浜市',
    prefecture: '神奈川県',
    center: { lat: 35.4437, lng: 139.6380 },
    zoom: 11
  },
  {
    id: 'sapporo',
    name: '札幌市',
    prefecture: '北海道',
    center: { lat: 43.0642, lng: 141.3469 },
    zoom: 10
  },
  {
    id: 'fukuoka',
    name: '福岡市',
    prefecture: '福岡県',
    center: { lat: 33.5904, lng: 130.4017 },
    zoom: 11
  },
  {
    id: 'sendai',
    name: '仙台市',
    prefecture: '宮城県',
    center: { lat: 38.2682, lng: 140.8694 },
    zoom: 11
  }
];

export const DATA_TYPES: DataType[] = [
  {
    id: 'bldg',
    name: '建築物モデル',
    description: '建物の3D形状データ',
    fileIdentifier: 'bldg'
  },
  {
    id: 'tran',
    name: '道路モデル',
    description: '道路ネットワークデータ',
    fileIdentifier: 'tran'
  },
  {
    id: 'luse',
    name: '土地利用モデル',
    description: '土地利用区分データ',
    fileIdentifier: 'luse'
  },
  {
    id: 'urf',
    name: '都市計画決定情報',
    description: '都市計画関連データ',
    fileIdentifier: 'urf'
  }
];

export const LOD_LEVELS: LODLevel[] = [
  {
    level: 'LOD1',
    description: '簡易モデル（箱型）',
    estimatedSize: '約50KB/建物'
  },
  {
    level: 'LOD2',
    description: '詳細モデル（屋根形状含む）',
    estimatedSize: '約150KB/建物'
  }
];

export const CANVAS_CONFIG = {
  BUILDING_COLOR: '#e5e7eb',
  BUILDING_SELECTED_COLOR: '#3b82f6',
  BUILDING_HOVER_COLOR: '#93c5fd',
  GRID_COLOR: '#f3f4f6',
  BACKGROUND_COLOR: '#ffffff'
};