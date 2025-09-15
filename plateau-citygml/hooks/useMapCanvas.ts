import { useEffect, useRef, useState, useCallback } from 'react';
import { Building, MapViewport } from '@/types';
import { CANVAS_CONFIG } from '@/lib/constants';

export function useMapCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [buildings, setBuildings] = useState<Building[]>([]);
  const [selectedBuildings, setSelectedBuildings] = useState<Set<string>>(new Set());
  const [viewport, setViewport] = useState<MapViewport>({
    width: 800,
    height: 600,
    offsetX: 0,
    offsetY: 0,
    scale: 1
  });

  useEffect(() => {
    // Generate mock buildings for demonstration
    const mockBuildings: Building[] = [];
    for (let i = 0; i < 50; i++) {
      mockBuildings.push({
        id: `building-${i}`,
        x: Math.random() * 700 + 50,
        y: Math.random() * 500 + 50,
        width: 30 + Math.random() * 40,
        height: 30 + Math.random() * 40,
        selected: false,
        metadata: {
          name: `Building ${i + 1}`,
          floors: Math.floor(Math.random() * 10) + 1
        }
      });
    }
    setBuildings(mockBuildings);
  }, []);

  const drawCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear canvas
    ctx.fillStyle = CANVAS_CONFIG.BACKGROUND_COLOR;
    ctx.fillRect(0, 0, viewport.width, viewport.height);

    // Draw grid
    ctx.strokeStyle = CANVAS_CONFIG.GRID_COLOR;
    ctx.lineWidth = 0.5;
    for (let x = 0; x < viewport.width; x += 50) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, viewport.height);
      ctx.stroke();
    }
    for (let y = 0; y < viewport.height; y += 50) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(viewport.width, y);
      ctx.stroke();
    }

    // Draw buildings
    buildings.forEach(building => {
      const x = (building.x + viewport.offsetX) * viewport.scale;
      const y = (building.y + viewport.offsetY) * viewport.scale;
      const width = building.width * viewport.scale;
      const height = building.height * viewport.scale;

      ctx.fillStyle = selectedBuildings.has(building.id)
        ? CANVAS_CONFIG.BUILDING_SELECTED_COLOR
        : CANVAS_CONFIG.BUILDING_COLOR;
      
      ctx.fillRect(x, y, width, height);
      ctx.strokeStyle = '#9ca3af';
      ctx.lineWidth = 1;
      ctx.strokeRect(x, y, width, height);
    });
  }, [buildings, selectedBuildings, viewport]);

  useEffect(() => {
    drawCanvas();
  }, [drawCanvas]);

  const handleCanvasClick = useCallback((event: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = (event.clientX - rect.left) / viewport.scale - viewport.offsetX;
    const y = (event.clientY - rect.top) / viewport.scale - viewport.offsetY;

    // Find clicked building
    const clickedBuilding = buildings.find(building => {
      return x >= building.x && x <= building.x + building.width &&
             y >= building.y && y <= building.y + building.height;
    });

    if (clickedBuilding) {
      setSelectedBuildings(prev => {
        const newSet = new Set(prev);
        if (newSet.has(clickedBuilding.id)) {
          newSet.delete(clickedBuilding.id);
        } else {
          newSet.add(clickedBuilding.id);
        }
        return newSet;
      });
    }
  }, [buildings, viewport]);

  const zoomIn = useCallback(() => {
    setViewport(prev => ({ ...prev, scale: Math.min(prev.scale * 1.2, 3) }));
  }, []);

  const zoomOut = useCallback(() => {
    setViewport(prev => ({ ...prev, scale: Math.max(prev.scale / 1.2, 0.5) }));
  }, []);

  const resetView = useCallback(() => {
    setViewport(prev => ({ ...prev, scale: 1, offsetX: 0, offsetY: 0 }));
  }, []);

  return {
    canvasRef,
    buildings,
    selectedBuildings,
    viewport,
    handleCanvasClick,
    zoomIn,
    zoomOut,
    resetView,
    setViewport
  };
}