'use client';

import { useEffect, useRef, useState } from 'react';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';
import { useAppStore } from '@/lib/store/app-store';
import { Building } from '@/types';

// Mapbox public token (for demo purposes)
mapboxgl.accessToken = 'pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpejY4NXVycTA2emYycXBndHRqcmZ3N3gifQ.rJcFIG214AriISLbB6B5aw';

interface MapboxViewerProps {
  onBuildingSelect?: (buildingId: string) => void;
  onAreaSelect?: (bbox: { north: number; south: number; east: number; west: number }) => void;
}

export function MapboxViewer({ onBuildingSelect, onAreaSelect }: MapboxViewerProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);
  
  const {
    selectedBuildings,
    addBuilding,
    removeBuilding,
    setBoundingBox,
    viewMode,
    terrainEnabled,
  } = useAppStore();

  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    // Initialize map
    const mapInstance = new mapboxgl.Map({
      container: mapContainer.current,
      style: 'mapbox://styles/mapbox/dark-v11',
      center: [139.7670, 35.6812], // Tokyo
      zoom: 14,
      pitch: viewMode === '3D' ? 60 : 0,
      bearing: -17.6,
      antialias: true,
    });

    map.current = mapInstance;

    mapInstance.on('load', () => {
      setIsLoaded(true);

      // Add 3D buildings layer
      const layers = mapInstance.getStyle()?.layers;
      const labelLayerId = layers?.find(
        (layer) => layer.type === 'symbol' && layer.layout && layer.layout['text-field']
      )?.id;

      mapInstance.addLayer(
        {
          id: '3d-buildings',
          source: 'composite',
          'source-layer': 'building',
          filter: ['==', 'extrude', 'true'],
          type: 'fill-extrusion',
          minzoom: 15,
          paint: {
            'fill-extrusion-color': [
              'case',
              ['boolean', ['feature-state', 'selected'], false],
              '#00ffff',
              [
                'interpolate',
                ['linear'],
                ['get', 'height'],
                0, '#ddd',
                20, '#aaa',
                50, '#888',
                100, '#666',
                200, '#444',
              ],
            ],
            'fill-extrusion-height': [
              'interpolate',
              ['linear'],
              ['zoom'],
              15, 0,
              15.05, ['get', 'height'],
            ],
            'fill-extrusion-base': [
              'interpolate',
              ['linear'],
              ['zoom'],
              15, 0,
              15.05, ['get', 'min_height'],
            ],
            'fill-extrusion-opacity': 0.8,
          },
        },
        labelLayerId
      );

      // Add PLATEAU sample data as GeoJSON
      const sampleBuildings = generateSampleBuildings();
      
      mapInstance.addSource('plateau-buildings', {
        type: 'geojson',
        data: sampleBuildings,
      });

      mapInstance.addLayer({
        id: 'plateau-buildings-3d',
        type: 'fill-extrusion',
        source: 'plateau-buildings',
        paint: {
          'fill-extrusion-color': [
            'case',
            ['boolean', ['feature-state', 'selected'], false],
            '#00ffff',
            [
              'interpolate',
              ['linear'],
              ['get', 'height'],
              0, '#93c5fd',
              50, '#60a5fa',
              100, '#3b82f6',
              150, '#2563eb',
              200, '#1d4ed8',
            ],
          ],
          'fill-extrusion-height': ['get', 'height'],
          'fill-extrusion-base': 0,
          'fill-extrusion-opacity': 0.9,
        },
      });

      // Add click handler
      mapInstance.on('click', 'plateau-buildings-3d', (e) => {
        if (!e.features || e.features.length === 0) return;
        
        const feature = e.features[0];
        const buildingId = feature.properties?.id || `building-${Date.now()}`;
        
        if (selectedBuildings.has(buildingId)) {
          removeBuilding(buildingId);
          mapInstance.setFeatureState(
            { source: 'plateau-buildings', id: feature.id },
            { selected: false }
          );
        } else {
          const building: Building = {
            id: buildingId,
            gmlId: buildingId,
            x: 0,
            y: 0,
            z: 0,
            width: feature.properties?.width || 20,
            depth: feature.properties?.depth || 20,
            height: feature.properties?.height || 50,
            area: feature.properties?.area || 400,
            volume: feature.properties?.volume || 20000,
            selected: true,
            position: {
              longitude: e.lngLat.lng,
              latitude: e.lngLat.lat,
              altitude: 0,
            },
            metadata: {
              name: feature.properties?.name || 'Building',
              floors: Math.floor((feature.properties?.height || 50) / 3.5),
              usage: feature.properties?.usage || 'commercial',
            },
            lodData: {},
          };
          
          addBuilding(building);
          mapInstance.setFeatureState(
            { source: 'plateau-buildings', id: feature.id },
            { selected: true }
          );
          onBuildingSelect?.(buildingId);
        }
      });

      // Change cursor on hover
      mapInstance.on('mouseenter', 'plateau-buildings-3d', () => {
        mapInstance.getCanvas().style.cursor = 'pointer';
      });

      mapInstance.on('mouseleave', 'plateau-buildings-3d', () => {
        mapInstance.getCanvas().style.cursor = '';
      });

      // Add navigation controls
      mapInstance.addControl(new mapboxgl.NavigationControl(), 'top-right');
      mapInstance.addControl(new mapboxgl.ScaleControl(), 'bottom-left');
    });

    return () => {
      mapInstance.remove();
    };
  }, []);

  // Update view mode
  useEffect(() => {
    if (!map.current || !isLoaded) return;
    
    if (viewMode === '3D') {
      map.current.easeTo({
        pitch: 60,
        bearing: -17.6,
        duration: 1000,
      });
    } else if (viewMode === '2D') {
      map.current.easeTo({
        pitch: 0,
        bearing: 0,
        duration: 1000,
      });
    }
  }, [viewMode, isLoaded]);

  // Update terrain
  useEffect(() => {
    if (!map.current || !isLoaded) return;
    
    if (terrainEnabled) {
      map.current.setTerrain({ source: 'mapbox-dem', exaggeration: 1.5 });
      map.current.addSource('mapbox-dem', {
        type: 'raster-dem',
        url: 'mapbox://mapbox.mapbox-terrain-dem-v1',
        tileSize: 512,
        maxzoom: 14,
      });
    } else {
      map.current.setTerrain(null);
    }
  }, [terrainEnabled, isLoaded]);

  return (
    <div className="w-full h-full relative">
      <div ref={mapContainer} className="w-full h-full" />
      {!isLoaded && (
        <div className="absolute inset-0 bg-gray-900 flex items-center justify-center">
          <div className="text-white">
            <div className="animate-pulse flex flex-col items-center">
              <div className="w-16 h-16 bg-blue-500 rounded-full animate-bounce mb-4"></div>
              <p className="text-lg">3Dマップを初期化中...</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Generate sample PLATEAU-like buildings for Tokyo
function generateSampleBuildings(): GeoJSON.FeatureCollection {
  const buildings: GeoJSON.Feature[] = [];
  const baseCoords = [139.7670, 35.6812]; // Tokyo Station area
  
  // Generate a grid of buildings
  for (let i = 0; i < 50; i++) {
    const offsetLng = (Math.random() - 0.5) * 0.02;
    const offsetLat = (Math.random() - 0.5) * 0.02;
    const height = Math.random() * 150 + 20;
    const size = Math.random() * 0.0002 + 0.0001;
    
    const coords = [
      baseCoords[0] + offsetLng,
      baseCoords[1] + offsetLat,
    ];
    
    buildings.push({
      type: 'Feature',
      id: i,
      properties: {
        id: `tokyo-bldg-${i}`,
        name: `東京ビル ${i + 1}`,
        height: height,
        width: size * 111000,
        depth: size * 111000,
        area: size * size * 111000 * 111000,
        volume: size * size * 111000 * 111000 * height,
        usage: ['commercial', 'residential', 'office', 'mixed'][Math.floor(Math.random() * 4)],
        floors: Math.floor(height / 3.5),
        constructionYear: 1980 + Math.floor(Math.random() * 40),
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [coords[0] - size/2, coords[1] - size/2],
          [coords[0] + size/2, coords[1] - size/2],
          [coords[0] + size/2, coords[1] + size/2],
          [coords[0] - size/2, coords[1] + size/2],
          [coords[0] - size/2, coords[1] - size/2],
        ]],
      },
    });
  }
  
  return {
    type: 'FeatureCollection',
    features: buildings,
  };
}