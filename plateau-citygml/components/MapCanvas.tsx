'use client';

import { useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { ZoomIn, ZoomOut, RotateCcw } from 'lucide-react';
import { useMapCanvas } from '@/hooks/useMapCanvas';

interface MapCanvasProps {
  onSelectionChange?: (count: number) => void;
}

export function MapCanvas({ onSelectionChange }: MapCanvasProps) {
  const {
    canvasRef,
    selectedBuildings,
    viewport,
    handleCanvasClick,
    zoomIn,
    zoomOut,
    resetView,
    setViewport
  } = useMapCanvas();

  useEffect(() => {
    onSelectionChange?.(selectedBuildings.size);
  }, [selectedBuildings, onSelectionChange]);

  useEffect(() => {
    const handleResize = () => {
      if (canvasRef.current) {
        const parent = canvasRef.current.parentElement;
        if (parent) {
          setViewport(prev => ({
            ...prev,
            width: parent.clientWidth,
            height: parent.clientHeight
          }));
        }
      }
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [canvasRef, setViewport]);

  return (
    <div className="relative w-full h-full bg-gray-50 rounded-lg overflow-hidden">
      <canvas
        ref={canvasRef}
        width={viewport.width}
        height={viewport.height}
        className="cursor-pointer"
        onClick={handleCanvasClick}
      />
      
      <div className="absolute top-4 right-4 flex flex-col gap-2">
        <Button
          size="icon"
          variant="secondary"
          onClick={zoomIn}
          title="ズームイン"
        >
          <ZoomIn className="h-4 w-4" />
        </Button>
        <Button
          size="icon"
          variant="secondary"
          onClick={zoomOut}
          title="ズームアウト"
        >
          <ZoomOut className="h-4 w-4" />
        </Button>
        <Button
          size="icon"
          variant="secondary"
          onClick={resetView}
          title="リセット"
        >
          <RotateCcw className="h-4 w-4" />
        </Button>
      </div>

      <div className="absolute bottom-4 left-4 bg-white/90 backdrop-blur-sm rounded-lg px-3 py-2 text-sm">
        選択中: {selectedBuildings.size} 建物
      </div>
    </div>
  );
}