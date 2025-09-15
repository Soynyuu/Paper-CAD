'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Download, FileText, AlertCircle } from 'lucide-react';
import { RegionSelector } from './RegionSelector';
import { DataTypeSelector } from './DataTypeSelector';
import { LODSelector } from './LODSelector';
import { toast } from 'sonner';

interface DownloadPanelProps {
  selectedBuildingCount: number;
}

export function DownloadPanel({ selectedBuildingCount }: DownloadPanelProps) {
  const [region, setRegion] = useState('tokyo');
  const [dataTypes, setDataTypes] = useState<string[]>(['bldg']);
  const [lodLevel, setLodLevel] = useState('LOD1');
  const [isDownloading, setIsDownloading] = useState(false);

  const estimatedSize = () => {
    const baseSize = lodLevel === 'LOD1' ? 50 : 150;
    return (selectedBuildingCount * baseSize / 1024).toFixed(1);
  };

  const handleDownload = async () => {
    if (selectedBuildingCount === 0) {
      toast.error('建物を選択してください');
      return;
    }

    if (dataTypes.length === 0) {
      toast.error('データタイプを選択してください');
      return;
    }

    setIsDownloading(true);
    
    // Simulate download process
    setTimeout(() => {
      toast.success('ダウンロードを開始しました');
      setIsDownloading(false);
      
      // Create mock download
      const mockData = {
        region,
        dataTypes,
        lodLevel,
        buildingCount: selectedBuildingCount,
        timestamp: new Date().toISOString()
      };
      
      const blob = new Blob([JSON.stringify(mockData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `plateau_${region}_${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
    }, 2000);
  };

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>ダウンロード設定</CardTitle>
        <CardDescription>
          必要なデータを選択してダウンロード
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <RegionSelector value={region} onChange={setRegion} />
        
        <DataTypeSelector 
          selectedTypes={dataTypes} 
          onChange={setDataTypes} 
        />
        
        <LODSelector value={lodLevel} onChange={setLodLevel} />
        
        <div className="rounded-lg bg-blue-50 p-4 space-y-2">
          <div className="flex items-center gap-2 text-blue-600">
            <FileText className="h-4 w-4" />
            <span className="text-sm font-medium">ダウンロード情報</span>
          </div>
          <div className="text-sm space-y-1">
            <div className="flex justify-between">
              <span className="text-gray-600">選択建物数:</span>
              <span className="font-medium">{selectedBuildingCount} 棟</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">推定サイズ:</span>
              <span className="font-medium">約 {estimatedSize()} MB</span>
            </div>
          </div>
        </div>

        {selectedBuildingCount === 0 && (
          <div className="rounded-lg bg-yellow-50 p-4 flex items-start gap-2">
            <AlertCircle className="h-4 w-4 text-yellow-600 mt-0.5" />
            <p className="text-sm text-yellow-800">
              地図上から建物を選択してください
            </p>
          </div>
        )}

        <Button 
          className="w-full" 
          size="lg"
          onClick={handleDownload}
          disabled={selectedBuildingCount === 0 || isDownloading}
        >
          {isDownloading ? (
            <>処理中...</>
          ) : (
            <>
              <Download className="mr-2 h-4 w-4" />
              CityGMLをダウンロード
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  );
}