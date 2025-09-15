import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import type { Building, Region } from '@/types';

interface SelectionState {
  selectedBuildings: Map<string, Building>;
  selectedRegion: Region | null;
  selectedDataTypes: string[];
  lodLevel: 'LOD1' | 'LOD2' | 'LOD3';
  boundingBox: {
    north: number;
    south: number;
    east: number;
    west: number;
  } | null;
}

interface FilterState {
  minHeight: number;
  maxHeight: number;
  minArea: number;
  maxArea: number;
  buildingTypes: string[];
  constructionYear: {
    from: number | null;
    to: number | null;
  };
}

interface DownloadState {
  queue: Array<{
    id: string;
    status: 'pending' | 'processing' | 'completed' | 'failed';
    progress: number;
    url?: string;
    error?: string;
    createdAt: Date;
    estimatedSize: number;
  }>;
  currentDownload: string | null;
}

interface ViewState {
  cameraPosition: {
    longitude: number;
    latitude: number;
    height: number;
  };
  viewMode: '2D' | '3D' | 'COLUMBUS';
  terrainEnabled: boolean;
  shadowsEnabled: boolean;
  timeOfDay: Date;
  layersVisible: {
    buildings: boolean;
    roads: boolean;
    railways: boolean;
    vegetation: boolean;
    waterBodies: boolean;
  };
}

interface AppState extends SelectionState, FilterState, DownloadState, ViewState {
  // Selection actions
  addBuilding: (building: Building) => void;
  removeBuilding: (buildingId: string) => void;
  clearSelection: () => void;
  setSelectedRegion: (region: Region | null) => void;
  setSelectedDataTypes: (types: string[]) => void;
  setLodLevel: (level: 'LOD1' | 'LOD2' | 'LOD3') => void;
  setBoundingBox: (box: SelectionState['boundingBox']) => void;
  
  // Filter actions
  setHeightRange: (min: number, max: number) => void;
  setAreaRange: (min: number, max: number) => void;
  setBuildingTypes: (types: string[]) => void;
  setConstructionYearRange: (from: number | null, to: number | null) => void;
  
  // Download actions
  addToQueue: (download: DownloadState['queue'][0]) => void;
  updateQueueItem: (id: string, update: Partial<DownloadState['queue'][0]>) => void;
  removeFromQueue: (id: string) => void;
  setCurrentDownload: (id: string | null) => void;
  
  // View actions
  setCameraPosition: (position: ViewState['cameraPosition']) => void;
  setViewMode: (mode: ViewState['viewMode']) => void;
  toggleTerrain: () => void;
  toggleShadows: () => void;
  setTimeOfDay: (time: Date) => void;
  toggleLayer: (layer: keyof ViewState['layersVisible']) => void;
  
  // Utility
  getEstimatedDownloadSize: () => number;
  getSelectionStatistics: () => {
    buildingCount: number;
    totalArea: number;
    averageHeight: number;
    dataTypes: string[];
  };
}

export const useAppStore = create<AppState>()(
  devtools(
    persist(
      (set, get) => ({
        // Initial state
        selectedBuildings: new Map(),
        selectedRegion: null,
        selectedDataTypes: ['bldg'],
        lodLevel: 'LOD2',
        boundingBox: null,
        
        minHeight: 0,
        maxHeight: 500,
        minArea: 0,
        maxArea: 10000,
        buildingTypes: [],
        constructionYear: { from: null, to: null },
        
        queue: [],
        currentDownload: null,
        
        cameraPosition: {
          longitude: 139.6917,
          latitude: 35.6895,
          height: 10000,
        },
        viewMode: '3D',
        terrainEnabled: true,
        shadowsEnabled: true,
        timeOfDay: new Date(),
        layersVisible: {
          buildings: true,
          roads: true,
          railways: true,
          vegetation: true,
          waterBodies: true,
        },
        
        // Selection actions
        addBuilding: (building) =>
          set((state) => {
            const newBuildings = new Map(state.selectedBuildings);
            newBuildings.set(building.id, building);
            return { selectedBuildings: newBuildings };
          }),
          
        removeBuilding: (buildingId) =>
          set((state) => {
            const newBuildings = new Map(state.selectedBuildings);
            newBuildings.delete(buildingId);
            return { selectedBuildings: newBuildings };
          }),
          
        clearSelection: () =>
          set({ selectedBuildings: new Map(), boundingBox: null }),
          
        setSelectedRegion: (region) => set({ selectedRegion: region }),
        setSelectedDataTypes: (types) => set({ selectedDataTypes: types }),
        setLodLevel: (level) => set({ lodLevel: level }),
        setBoundingBox: (box) => set({ boundingBox: box }),
        
        // Filter actions
        setHeightRange: (min, max) =>
          set({ minHeight: min, maxHeight: max }),
          
        setAreaRange: (min, max) =>
          set({ minArea: min, maxArea: max }),
          
        setBuildingTypes: (types) => set({ buildingTypes: types }),
        
        setConstructionYearRange: (from, to) =>
          set({ constructionYear: { from, to } }),
        
        // Download actions
        addToQueue: (download) =>
          set((state) => ({ queue: [...state.queue, download] })),
          
        updateQueueItem: (id, update) =>
          set((state) => ({
            queue: state.queue.map((item) =>
              item.id === id ? { ...item, ...update } : item
            ),
          })),
          
        removeFromQueue: (id) =>
          set((state) => ({
            queue: state.queue.filter((item) => item.id !== id),
          })),
          
        setCurrentDownload: (id) => set({ currentDownload: id }),
        
        // View actions
        setCameraPosition: (position) =>
          set({ cameraPosition: position }),
          
        setViewMode: (mode) => set({ viewMode: mode }),
        
        toggleTerrain: () =>
          set((state) => ({ terrainEnabled: !state.terrainEnabled })),
          
        toggleShadows: () =>
          set((state) => ({ shadowsEnabled: !state.shadowsEnabled })),
          
        setTimeOfDay: (time) => set({ timeOfDay: time }),
        
        toggleLayer: (layer) =>
          set((state) => ({
            layersVisible: {
              ...state.layersVisible,
              [layer]: !state.layersVisible[layer],
            },
          })),
        
        // Utility functions
        getEstimatedDownloadSize: () => {
          const state = get();
          const buildingCount = state.selectedBuildings.size;
          const lodMultiplier = 
            state.lodLevel === 'LOD1' ? 0.05 :
            state.lodLevel === 'LOD2' ? 0.15 :
            0.5; // LOD3
          const dataTypeCount = state.selectedDataTypes.length;
          
          return buildingCount * lodMultiplier * dataTypeCount; // MB
        },
        
        getSelectionStatistics: () => {
          const state = get();
          const buildings = Array.from(state.selectedBuildings.values());
          
          return {
            buildingCount: buildings.length,
            totalArea: buildings.reduce((sum, b) => sum + (b.area || 0), 0),
            averageHeight: buildings.length > 0
              ? buildings.reduce((sum, b) => sum + (b.height || 0), 0) / buildings.length
              : 0,
            dataTypes: state.selectedDataTypes,
          };
        },
      }),
      {
        name: 'plateau-app-store',
        partialize: (state) => ({
          selectedRegion: state.selectedRegion,
          lodLevel: state.lodLevel,
          viewMode: state.viewMode,
          cameraPosition: state.cameraPosition,
          layersVisible: state.layersVisible,
        }),
      }
    )
  )
);