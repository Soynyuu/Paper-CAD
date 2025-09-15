'use client';

import { useEffect, useRef, useState } from 'react';
import { Viewer, Entity, CameraFlyTo, Globe, Scene, Camera } from 'resium';
import * as Cesium from 'cesium';
import { useAppStore } from '@/lib/store/app-store';
import { PlateauDataset } from '@/types';

// Set Cesium Ion default access token
if (typeof window !== 'undefined' && !Cesium.Ion.defaultAccessToken) {
  Cesium.Ion.defaultAccessToken = process.env.NEXT_PUBLIC_CESIUM_ION_TOKEN || '';
}

interface CesiumViewerProps {
  datasets?: PlateauDataset[];
  onBuildingSelect?: (buildingId: string) => void;
  onAreaSelect?: (bbox: { north: number; south: number; east: number; west: number }) => void;
}

export function CesiumViewer({ datasets, onBuildingSelect, onAreaSelect }: CesiumViewerProps) {
  const viewerRef = useRef<Cesium.Viewer | null>(null);
  const [isClient, setIsClient] = useState(false);
  const [tilesets, setTilesets] = useState<Cesium.Cesium3DTileset[]>([]);
  const [selectedEntity, setSelectedEntity] = useState<Cesium.Entity | null>(null);
  
  const {
    cameraPosition,
    viewMode,
    terrainEnabled,
    shadowsEnabled,
    timeOfDay,
    layersVisible,
    selectedBuildings,
    addBuilding,
    removeBuilding,
    setBoundingBox,
  } = useAppStore();

  useEffect(() => {
    setIsClient(true);
  }, []);

  useEffect(() => {
    if (!viewerRef.current || !isClient) return;
    
    const viewer = viewerRef.current;
    
    // Enable terrain
    if (terrainEnabled) {
      Cesium.createWorldTerrainAsync({
        requestWaterMask: true,
        requestVertexNormals: true,
      }).then(terrainProvider => {
        viewer.terrainProvider = terrainProvider;
      });
    } else {
      viewer.terrainProvider = new Cesium.EllipsoidTerrainProvider();
    }
    
    // Configure shadows
    viewer.shadows = shadowsEnabled;
    viewer.shadowMap.enabled = shadowsEnabled;
    
    // Set time of day
    viewer.clock.currentTime = Cesium.JulianDate.fromDate(timeOfDay);
    
    // Configure scene
    viewer.scene.globe.enableLighting = shadowsEnabled;
    viewer.scene.globe.depthTestAgainstTerrain = true;
    
    // Add atmosphere effects
    viewer.scene.globe.showGroundAtmosphere = true;
    
    // Configure fog properly
    viewer.scene.fog.enabled = true;
    viewer.scene.fog.density = 2.0e-4;
    viewer.scene.fog.screenSpaceErrorFactor = 2.0;
    
  }, [terrainEnabled, shadowsEnabled, timeOfDay, isClient]);

  // Load 3D Tiles datasets
  useEffect(() => {
    if (!viewerRef.current || !datasets || !isClient) return;
    
    const viewer = viewerRef.current;
    const newTilesets: Cesium.Cesium3DTileset[] = [];
    
    datasets.forEach(async (dataset) => {
      if (dataset.tilesetUrl) {
        try {
          const tileset = viewer.scene.primitives.add(
            new Cesium.Cesium3DTileset({
              url: dataset.tilesetUrl,
              maximumScreenSpaceError: 2,
              maximumMemoryUsage: 512,
              dynamicScreenSpaceError: true,
              dynamicScreenSpaceErrorDensity: 0.00278,
              dynamicScreenSpaceErrorFactor: 4.0,
              skipLevelOfDetail: true,
              baseScreenSpaceError: 1024,
              skipScreenSpaceErrorFactor: 16,
              skipLevels: 1,
              immediatelyLoadDesiredLevelOfDetail: false,
              loadSiblings: false,
              cullWithChildrenBounds: true,
            })
          );
          
          // Style buildings based on selection
          tileset.style = new Cesium.Cesium3DTileStyle({
            color: {
              conditions: [
                ['${selected} === true', 'color("cyan", 0.9)'],
                ['${height} > 100', 'color("purple", 0.5)'],
                ['${height} > 50', 'color("red", 0.5)'],
                ['${height} > 20', 'color("orange", 0.5)'],
                ['true', 'color("white", 0.5)'],
              ],
            },
            show: layersVisible.buildings,
          });
          
          // Handle tile load events
          tileset.readyPromise.then(() => {
            viewer.zoomTo(tileset);
          });
          
          newTilesets.push(tileset);
        } catch (error) {
          console.error('Failed to load tileset:', dataset.tilesetUrl, error);
        }
      }
    });
    
    setTilesets(newTilesets);
    
    return () => {
      newTilesets.forEach(tileset => {
        viewer.scene.primitives.remove(tileset);
      });
    };
  }, [datasets, layersVisible.buildings, isClient]);

  // Handle click events
  useEffect(() => {
    if (!viewerRef.current || !isClient) return;
    
    const viewer = viewerRef.current;
    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
    
    // Left click - select building
    handler.setInputAction((click: Cesium.ScreenSpaceEventHandler.PositionedEvent) => {
      const pickedFeature = viewer.scene.pick(click.position);
      
      if (Cesium.defined(pickedFeature)) {
        // Handle 3D Tiles feature
        if (pickedFeature instanceof Cesium.Cesium3DTileFeature) {
          const properties = pickedFeature.getPropertyNames();
          const buildingData: any = {};
          
          properties.forEach((prop: string) => {
            buildingData[prop] = pickedFeature.getProperty(prop);
          });
          
          if (buildingData.gmlId || buildingData.id) {
            const buildingId = buildingData.gmlId || buildingData.id;
            
            // Toggle selection
            if (selectedBuildings.has(buildingId)) {
              removeBuilding(buildingId);
              pickedFeature.setProperty('selected', false);
            } else {
              const building = {
                id: buildingId,
                gmlId: buildingData.gmlId || buildingId,
                x: 0, y: 0, z: 0,
                width: buildingData.width || 0,
                depth: buildingData.depth || 0,
                height: buildingData.measuredHeight || buildingData.height || 0,
                area: buildingData.area || 0,
                volume: buildingData.volume || 0,
                selected: true,
                position: {
                  longitude: buildingData.longitude || 0,
                  latitude: buildingData.latitude || 0,
                  altitude: buildingData.altitude || 0,
                },
                metadata: {
                  name: buildingData.name,
                  address: buildingData.address,
                  floors: buildingData.storeysAboveGround,
                  usage: buildingData.usage,
                  constructionYear: buildingData.yearOfConstruction,
                  measuredHeight: buildingData.measuredHeight,
                  roofType: buildingData.roofType,
                  wallMaterial: buildingData.wallSurfaceMaterial,
                },
                lodData: {},
              };
              
              addBuilding(building);
              pickedFeature.setProperty('selected', true);
              onBuildingSelect?.(buildingId);
            }
          }
        }
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
    
    // Shift + drag - area selection
    let drawing = false;
    let startPosition: Cesium.Cartesian2 | null = null;
    let endPosition: Cesium.Cartesian2 | null = null;
    let selectionRectangle: Cesium.Entity | null = null;
    
    handler.setInputAction((click: Cesium.ScreenSpaceEventHandler.PositionedEvent) => {
      if (!viewer.scene.pickPositionSupported) return;
      
      drawing = true;
      startPosition = click.position;
      
      // Create selection rectangle entity
      selectionRectangle = viewer.entities.add({
        rectangle: {
          coordinates: Cesium.Rectangle.fromDegrees(0, 0, 0, 0),
          material: Cesium.Color.CYAN.withAlpha(0.3),
          outline: true,
          outlineColor: Cesium.Color.CYAN,
          outlineWidth: 2,
        },
      });
    }, Cesium.ScreenSpaceEventType.LEFT_DOWN, Cesium.KeyboardEventModifier.SHIFT);
    
    handler.setInputAction((movement: Cesium.ScreenSpaceEventHandler.MotionEvent) => {
      if (!drawing || !startPosition || !selectionRectangle) return;
      
      endPosition = movement.endPosition;
      
      const startCartesian = viewer.camera.pickEllipsoid(startPosition, viewer.scene.globe.ellipsoid);
      const endCartesian = viewer.camera.pickEllipsoid(endPosition, viewer.scene.globe.ellipsoid);
      
      if (startCartesian && endCartesian) {
        const startCartographic = Cesium.Cartographic.fromCartesian(startCartesian);
        const endCartographic = Cesium.Cartographic.fromCartesian(endCartesian);
        
        const west = Math.min(startCartographic.longitude, endCartographic.longitude);
        const east = Math.max(startCartographic.longitude, endCartographic.longitude);
        const south = Math.min(startCartographic.latitude, endCartographic.latitude);
        const north = Math.max(startCartographic.latitude, endCartographic.latitude);
        
        selectionRectangle.rectangle!.coordinates = new Cesium.ConstantProperty(
          Cesium.Rectangle.fromRadians(west, south, east, north)
        );
      }
    }, Cesium.ScreenSpaceEventType.MOUSE_MOVE, Cesium.KeyboardEventModifier.SHIFT);
    
    handler.setInputAction(() => {
      if (!drawing || !startPosition || !endPosition || !selectionRectangle) return;
      
      drawing = false;
      
      const startCartesian = viewer.camera.pickEllipsoid(startPosition, viewer.scene.globe.ellipsoid);
      const endCartesian = viewer.camera.pickEllipsoid(endPosition, viewer.scene.globe.ellipsoid);
      
      if (startCartesian && endCartesian) {
        const startCartographic = Cesium.Cartographic.fromCartesian(startCartesian);
        const endCartographic = Cesium.Cartographic.fromCartesian(endCartesian);
        
        const bbox = {
          west: Cesium.Math.toDegrees(Math.min(startCartographic.longitude, endCartographic.longitude)),
          east: Cesium.Math.toDegrees(Math.max(startCartographic.longitude, endCartographic.longitude)),
          south: Cesium.Math.toDegrees(Math.min(startCartographic.latitude, endCartographic.latitude)),
          north: Cesium.Math.toDegrees(Math.max(startCartographic.latitude, endCartographic.latitude)),
        };
        
        setBoundingBox(bbox);
        onAreaSelect?.(bbox);
        
        // Select all buildings within bounding box
        tilesets.forEach(tileset => {
          tileset.style = new Cesium.Cesium3DTileStyle({
            color: {
              conditions: [
                [`\${longitude} >= ${bbox.west} && \${longitude} <= ${bbox.east} && \${latitude} >= ${bbox.south} && \${latitude} <= ${bbox.north}`, 'color("cyan", 0.9)'],
                ['${height} > 100', 'color("purple", 0.5)'],
                ['${height} > 50', 'color("red", 0.5)'],
                ['${height} > 20', 'color("orange", 0.5)'],
                ['true', 'color("white", 0.5)'],
              ],
            },
          });
        });
      }
      
      // Remove selection rectangle after a delay
      setTimeout(() => {
        if (selectionRectangle) {
          viewer.entities.remove(selectionRectangle);
          selectionRectangle = null;
        }
      }, 2000);
      
      startPosition = null;
      endPosition = null;
    }, Cesium.ScreenSpaceEventType.LEFT_UP, Cesium.KeyboardEventModifier.SHIFT);
    
    return () => {
      handler.destroy();
    };
  }, [selectedBuildings, addBuilding, removeBuilding, onBuildingSelect, onAreaSelect, setBoundingBox, tilesets, isClient]);

  if (!isClient) {
    return <div className="w-full h-full bg-gray-900 animate-pulse" />;
  }

  return (
    <Viewer
      ref={(ref: any) => {
        if (ref?.cesiumElement) {
          viewerRef.current = ref.cesiumElement;
        }
      }}
      full
      timeline={false}
      animation={false}
      baseLayerPicker={false}
      geocoder={false}
      homeButton={false}
      sceneModePicker={true}
      navigationHelpButton={false}
      creditContainer={document.createElement('div')}
      imageryProvider={
        new Cesium.IonImageryProvider({
          assetId: 2,
        })
      }
      sceneMode={
        viewMode === '2D'
          ? Cesium.SceneMode.SCENE2D
          : viewMode === 'COLUMBUS'
          ? Cesium.SceneMode.COLUMBUS_VIEW
          : Cesium.SceneMode.SCENE3D
      }
    >
      <Globe enableLighting={shadowsEnabled} />
      <Scene />
      <Camera />
      <CameraFlyTo
        destination={Cesium.Cartesian3.fromDegrees(
          cameraPosition.longitude,
          cameraPosition.latitude,
          cameraPosition.height
        )}
        duration={2}
      />
    </Viewer>
  );
}