'use client';

import { useEffect, useRef, useState } from 'react';
import * as Cesium from 'cesium';
import { useAppStore } from '@/lib/store/app-store';
import { PlateauDataset } from '@/types';

// Set Cesium Ion default access token
if (typeof window !== 'undefined') {
  Cesium.Ion.defaultAccessToken = process.env.NEXT_PUBLIC_CESIUM_ION_TOKEN || '';
}

interface SimpleCesiumViewerProps {
  datasets?: PlateauDataset[];
  onBuildingSelect?: (buildingId: string) => void;
  onAreaSelect?: (bbox: { north: number; south: number; east: number; west: number }) => void;
}

export function SimpleCesiumViewer({ datasets, onBuildingSelect, onAreaSelect }: SimpleCesiumViewerProps) {
  const viewerRef = useRef<Cesium.Viewer | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isReady, setIsReady] = useState(false);
  
  const {
    cameraPosition,
    viewMode,
    terrainEnabled,
    shadowsEnabled,
    selectedBuildings,
    addBuilding,
    removeBuilding,
    setBoundingBox,
  } = useAppStore();

  useEffect(() => {
    if (!containerRef.current) return;

    // Initialize Cesium Viewer
    const viewer = new Cesium.Viewer(containerRef.current, {
      terrainProvider: undefined,
      baseLayerPicker: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: true,
      navigationHelpButton: false,
      animation: false,
      timeline: false,
      creditContainer: document.createElement('div'),
      imageryProvider: new Cesium.UrlTemplateImageryProvider({
        url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
        credit: 'OpenStreetMap contributors',
      }),
      requestRenderMode: true,
      maximumRenderTimeChange: Infinity,
    });

    viewerRef.current = viewer;
    setIsReady(true);

    // Set initial camera position (Tokyo)
    viewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(
        139.7670, // Tokyo longitude
        35.6812,  // Tokyo latitude
        15000     // Height in meters
      ),
      orientation: {
        heading: Cesium.Math.toRadians(0),
        pitch: Cesium.Math.toRadians(-45),
        roll: 0,
      },
    });

    // Basic scene configuration
    viewer.scene.globe.enableLighting = false;
    viewer.scene.globe.depthTestAgainstTerrain = true;
    viewer.scene.globe.showGroundAtmosphere = true;

    return () => {
      viewer.destroy();
    };
  }, []);

  // Update terrain
  useEffect(() => {
    if (!viewerRef.current || !isReady) return;
    
    const viewer = viewerRef.current;
    
    if (terrainEnabled) {
      Cesium.createWorldTerrainAsync({
        requestWaterMask: true,
        requestVertexNormals: true,
      }).then(terrainProvider => {
        viewer.terrainProvider = terrainProvider;
      }).catch(() => {
        // Fallback to ellipsoid if terrain fails
        viewer.terrainProvider = new Cesium.EllipsoidTerrainProvider();
      });
    } else {
      viewer.terrainProvider = new Cesium.EllipsoidTerrainProvider();
    }
  }, [terrainEnabled, isReady]);

  // Update shadows and lighting
  useEffect(() => {
    if (!viewerRef.current || !isReady) return;
    
    const viewer = viewerRef.current;
    viewer.shadows = shadowsEnabled;
    viewer.scene.globe.enableLighting = shadowsEnabled;
  }, [shadowsEnabled, isReady]);

  // Update view mode
  useEffect(() => {
    if (!viewerRef.current || !isReady) return;
    
    const viewer = viewerRef.current;
    
    if (viewMode === '2D') {
      viewer.scene.mode = Cesium.SceneMode.SCENE2D;
    } else if (viewMode === 'COLUMBUS') {
      viewer.scene.mode = Cesium.SceneMode.COLUMBUS_VIEW;
    } else {
      viewer.scene.mode = Cesium.SceneMode.SCENE3D;
    }
  }, [viewMode, isReady]);

  // Load 3D Tiles datasets
  useEffect(() => {
    if (!viewerRef.current || !datasets || !isReady) return;
    
    const viewer = viewerRef.current;
    const tilesets: Cesium.Cesium3DTileset[] = [];
    
    // Load OSM Buildings for Tokyo area
    const osmBuildings = viewer.scene.primitives.add(
      Cesium.createOsmBuildingsAsync()
    );
    
    // Also try to load sample 3D buildings from Cesium Ion
    try {
      const sampleTileset = viewer.scene.primitives.add(
        new Cesium.Cesium3DTileset({
          url: Cesium.IonResource.fromAssetId(96188), // Cesium OSM Buildings
          maximumScreenSpaceError: 8,
          maximumMemoryUsage: 256,
        })
      );
      
      sampleTileset.readyPromise.then(() => {
        // Apply styling
        sampleTileset.style = new Cesium.Cesium3DTileStyle({
          color: {
            conditions: [
              ['${feature["building:levels"]} > 20', 'color("purple", 0.8)'],
              ['${feature["building:levels"]} > 10', 'color("red", 0.8)'],
              ['${feature["building:levels"]} > 5', 'color("orange", 0.8)'],
              ['true', 'color("lightblue", 0.8)'],
            ],
          },
          show: true,
        });
      }).catch(console.error);
      
      tilesets.push(sampleTileset);
    } catch (error) {
      console.log('Could not load Cesium Ion buildings, using OSM buildings only');
    }
    
    // Load PLATEAU datasets if available
    datasets.forEach(async (dataset) => {
      if (dataset.tilesetUrl) {
        try {
          const tileset = viewer.scene.primitives.add(
            new Cesium.Cesium3DTileset({
              url: dataset.tilesetUrl,
              maximumScreenSpaceError: 8,
              maximumMemoryUsage: 256,
            })
          );
          
          tileset.readyPromise.then(() => {
            console.log('Loaded tileset:', dataset.title);
          }).catch(console.error);
          
          tilesets.push(tileset);
        } catch (error) {
          console.error('Failed to load tileset:', dataset.tilesetUrl, error);
        }
      }
    });
    
    return () => {
      tilesets.forEach(tileset => {
        viewer.scene.primitives.remove(tileset);
      });
    };
  }, [datasets, isReady]);

  // Handle click events
  useEffect(() => {
    if (!viewerRef.current || !isReady) return;
    
    const viewer = viewerRef.current;
    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
    
    // Left click - select building
    handler.setInputAction((click: any) => {
      const pickedFeature = viewer.scene.pick(click.position);
      
      if (Cesium.defined(pickedFeature)) {
        // Handle 3D Tiles feature
        if (pickedFeature instanceof Cesium.Cesium3DTileFeature) {
          const properties = pickedFeature.getPropertyIds();
          const buildingData: any = {};
          
          properties.forEach((prop: string) => {
            buildingData[prop] = pickedFeature.getProperty(prop);
          });
          
          console.log('Clicked building:', buildingData);
          
          // Create a simple ID from properties
          const buildingId = buildingData.id || buildingData.name || `building-${Date.now()}`;
          
          // Toggle selection
          if (selectedBuildings.has(buildingId)) {
            removeBuilding(buildingId);
          } else {
            const building = {
              id: buildingId,
              gmlId: buildingId,
              x: 0, y: 0, z: 0,
              width: 10,
              depth: 10,
              height: buildingData.Height || buildingData.height || 20,
              area: 100,
              volume: 2000,
              selected: true,
              position: {
                longitude: 0,
                latitude: 0,
                altitude: 0,
              },
              metadata: {
                name: buildingData.name || buildingId,
              },
              lodData: {},
            };
            
            addBuilding(building);
            onBuildingSelect?.(buildingId);
          }
        }
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
    
    return () => {
      handler.destroy();
    };
  }, [selectedBuildings, addBuilding, removeBuilding, onBuildingSelect, isReady]);

  return (
    <div className="w-full h-full relative">
      <div ref={containerRef} className="w-full h-full" />
      {!isReady && (
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