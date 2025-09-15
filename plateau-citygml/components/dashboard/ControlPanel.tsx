'use client';

import { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { 
  Download, Filter, Layers, Settings, Search, MapPin, 
  Building, Calendar, Ruler, Database, Globe, Sun, Moon,
  Eye, EyeOff, Zap, AlertCircle, CheckCircle, Clock
} from 'lucide-react';
import { useAppStore } from '@/lib/store/app-store';
import { REGIONS, DATA_TYPES, LOD_LEVELS } from '@/lib/constants';
import { format } from 'date-fns';
import { ja } from 'date-fns/locale';

export function ControlPanel() {
  const {
    selectedBuildings,
    selectedRegion,
    selectedDataTypes,
    lodLevel,
    minHeight,
    maxHeight,
    minArea,
    maxArea,
    buildingTypes,
    constructionYear,
    queue,
    terrainEnabled,
    shadowsEnabled,
    layersVisible,
    viewMode,
    setSelectedRegion,
    setSelectedDataTypes,
    setLodLevel,
    setHeightRange,
    setAreaRange,
    setBuildingTypes,
    setConstructionYearRange,
    toggleTerrain,
    toggleShadows,
    toggleLayer,
    setViewMode,
    clearSelection,
    getEstimatedDownloadSize,
    getSelectionStatistics,
  } = useAppStore();

  const [activeTab, setActiveTab] = useState('selection');
  const stats = getSelectionStatistics();
  const estimatedSize = getEstimatedDownloadSize();

  const buildingTypeOptions = [
    { value: 'residential', label: '住宅' },
    { value: 'commercial', label: '商業施設' },
    { value: 'office', label: 'オフィスビル' },
    { value: 'industrial', label: '工業施設' },
    { value: 'public', label: '公共施設' },
    { value: 'educational', label: '教育施設' },
    { value: 'medical', label: '医療施設' },
    { value: 'transportation', label: '交通施設' },
  ];

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between">
          <span>PLATEAU データ選択</span>
          <Badge variant="secondary" className="ml-2">
            Pro
          </Badge>
        </CardTitle>
        <CardDescription>
          3D都市モデルの選択とダウンロード
        </CardDescription>
      </CardHeader>
      
      <CardContent className="flex-1 overflow-hidden p-0">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full flex flex-col">
          <TabsList className="grid w-full grid-cols-4 px-6">
            <TabsTrigger value="selection" className="text-xs">
              <MapPin className="w-3 h-3 mr-1" />
              選択
            </TabsTrigger>
            <TabsTrigger value="filter" className="text-xs">
              <Filter className="w-3 h-3 mr-1" />
              フィルタ
            </TabsTrigger>
            <TabsTrigger value="view" className="text-xs">
              <Layers className="w-3 h-3 mr-1" />
              表示
            </TabsTrigger>
            <TabsTrigger value="download" className="text-xs">
              <Download className="w-3 h-3 mr-1" />
              DL
            </TabsTrigger>
          </TabsList>
          
          <ScrollArea className="flex-1">
            <div className="p-6">
              <TabsContent value="selection" className="mt-0 space-y-4">
                {/* Region Selection */}
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <Globe className="w-4 h-4" />
                    地域選択
                  </Label>
                  <Select
                    value={selectedRegion?.id}
                    onValueChange={(value) => {
                      const region = REGIONS.find(r => r.id === value);
                      setSelectedRegion(region || null);
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="地域を選択" />
                    </SelectTrigger>
                    <SelectContent>
                      {REGIONS.map((region) => (
                        <SelectItem key={region.id} value={region.id}>
                          <div className="flex items-center justify-between w-full">
                            <span>{region.prefecture} - {region.name}</span>
                            <Badge variant="outline" className="ml-2">
                              2024
                            </Badge>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Data Types */}
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <Database className="w-4 h-4" />
                    データタイプ
                  </Label>
                  <div className="grid grid-cols-2 gap-2">
                    {DATA_TYPES.map((type) => (
                      <Button
                        key={type.id}
                        variant={selectedDataTypes.includes(type.id) ? 'default' : 'outline'}
                        size="sm"
                        className="justify-start"
                        onClick={() => {
                          if (selectedDataTypes.includes(type.id)) {
                            setSelectedDataTypes(selectedDataTypes.filter(t => t !== type.id));
                          } else {
                            setSelectedDataTypes([...selectedDataTypes, type.id]);
                          }
                        }}
                      >
                        <span className="truncate">{type.name}</span>
                      </Button>
                    ))}
                  </div>
                </div>

                {/* LOD Level */}
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <Zap className="w-4 h-4" />
                    詳細度 (LOD)
                  </Label>
                  <Select value={lodLevel} onValueChange={(value: any) => setLodLevel(value)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {LOD_LEVELS.map((lod) => (
                        <SelectItem key={lod.level} value={lod.level}>
                          <div>
                            <div className="font-medium">{lod.level}</div>
                            <div className="text-xs text-muted-foreground">
                              {lod.description}
                            </div>
                          </div>
                        </SelectItem>
                      ))}
                      <SelectItem value="LOD3">
                        <div>
                          <div className="font-medium flex items-center gap-1">
                            LOD3
                            <Badge variant="secondary" className="text-xs">Pro</Badge>
                          </div>
                          <div className="text-xs text-muted-foreground">
                            詳細モデル（テクスチャ含む）
                          </div>
                        </div>
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* Selection Stats */}
                <Card className="bg-secondary/50">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Building className="w-4 h-4" />
                      選択状況
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">選択建物数</span>
                      <span className="font-medium">{stats.buildingCount.toLocaleString()} 棟</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">総面積</span>
                      <span className="font-medium">{stats.totalArea.toLocaleString()} m²</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">平均高さ</span>
                      <span className="font-medium">{stats.averageHeight.toFixed(1)} m</span>
                    </div>
                    <Separator className="my-2" />
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">推定サイズ</span>
                      <span className="font-medium">{estimatedSize.toFixed(1)} MB</span>
                    </div>
                  </CardContent>
                </Card>

                <Button 
                  variant="outline" 
                  className="w-full"
                  onClick={clearSelection}
                  disabled={selectedBuildings.size === 0}
                >
                  選択をクリア
                </Button>
              </TabsContent>

              <TabsContent value="filter" className="mt-0 space-y-4">
                {/* Height Filter */}
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <Ruler className="w-4 h-4" />
                    高さ範囲 ({minHeight}m - {maxHeight}m)
                  </Label>
                  <Slider
                    value={[minHeight, maxHeight]}
                    onValueChange={([min, max]) => setHeightRange(min, max)}
                    min={0}
                    max={500}
                    step={10}
                    className="w-full"
                  />
                </div>

                {/* Area Filter */}
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <Building className="w-4 h-4" />
                    面積範囲 ({minArea}m² - {maxArea}m²)
                  </Label>
                  <Slider
                    value={[minArea, maxArea]}
                    onValueChange={([min, max]) => setAreaRange(min, max)}
                    min={0}
                    max={10000}
                    step={100}
                    className="w-full"
                  />
                </div>

                {/* Building Type Filter */}
                <div className="space-y-2">
                  <Label>建物用途</Label>
                  <div className="grid grid-cols-2 gap-2">
                    {buildingTypeOptions.map((type) => (
                      <Button
                        key={type.value}
                        variant={buildingTypes.includes(type.value) ? 'default' : 'outline'}
                        size="sm"
                        className="justify-start text-xs"
                        onClick={() => {
                          if (buildingTypes.includes(type.value)) {
                            setBuildingTypes(buildingTypes.filter(t => t !== type.value));
                          } else {
                            setBuildingTypes([...buildingTypes, type.value]);
                          }
                        }}
                      >
                        {type.label}
                      </Button>
                    ))}
                  </div>
                </div>

                {/* Construction Year Filter */}
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <Calendar className="w-4 h-4" />
                    建築年
                  </Label>
                  <div className="flex gap-2">
                    <Input
                      type="number"
                      placeholder="開始年"
                      value={constructionYear.from || ''}
                      onChange={(e) => setConstructionYearRange(
                        e.target.value ? parseInt(e.target.value) : null,
                        constructionYear.to
                      )}
                      min={1900}
                      max={2024}
                    />
                    <span className="self-center">〜</span>
                    <Input
                      type="number"
                      placeholder="終了年"
                      value={constructionYear.to || ''}
                      onChange={(e) => setConstructionYearRange(
                        constructionYear.from,
                        e.target.value ? parseInt(e.target.value) : null
                      )}
                      min={1900}
                      max={2024}
                    />
                  </div>
                </div>

                <Button className="w-full">
                  <Search className="w-4 h-4 mr-2" />
                  フィルタを適用
                </Button>
              </TabsContent>

              <TabsContent value="view" className="mt-0 space-y-4">
                {/* View Mode */}
                <div className="space-y-2">
                  <Label>ビューモード</Label>
                  <div className="grid grid-cols-3 gap-2">
                    {['2D', '3D', 'COLUMBUS'].map((mode) => (
                      <Button
                        key={mode}
                        variant={viewMode === mode ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setViewMode(mode as any)}
                      >
                        {mode}
                      </Button>
                    ))}
                  </div>
                </div>

                {/* Terrain Toggle */}
                <div className="flex items-center justify-between">
                  <Label htmlFor="terrain" className="flex items-center gap-2">
                    <Globe className="w-4 h-4" />
                    地形表示
                  </Label>
                  <Switch
                    id="terrain"
                    checked={terrainEnabled}
                    onCheckedChange={toggleTerrain}
                  />
                </div>

                {/* Shadows Toggle */}
                <div className="flex items-center justify-between">
                  <Label htmlFor="shadows" className="flex items-center gap-2">
                    {shadowsEnabled ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
                    影の表示
                  </Label>
                  <Switch
                    id="shadows"
                    checked={shadowsEnabled}
                    onCheckedChange={toggleShadows}
                  />
                </div>

                <Separator />

                {/* Layer Toggles */}
                <div className="space-y-3">
                  <Label>レイヤー表示</Label>
                  {Object.entries(layersVisible).map(([key, visible]) => (
                    <div key={key} className="flex items-center justify-between">
                      <Label htmlFor={key} className="flex items-center gap-2 text-sm">
                        {visible ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
                        {key === 'buildings' && '建築物'}
                        {key === 'roads' && '道路'}
                        {key === 'railways' && '鉄道'}
                        {key === 'vegetation' && '植生'}
                        {key === 'waterBodies' && '水域'}
                      </Label>
                      <Switch
                        id={key}
                        checked={visible}
                        onCheckedChange={() => toggleLayer(key as any)}
                        className="scale-90"
                      />
                    </div>
                  ))}
                </div>
              </TabsContent>

              <TabsContent value="download" className="mt-0 space-y-4">
                {/* Download Queue */}
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <Clock className="w-4 h-4" />
                    ダウンロードキュー
                  </Label>
                  
                  {queue.length === 0 ? (
                    <Card className="bg-secondary/50">
                      <CardContent className="py-8 text-center text-muted-foreground">
                        <Download className="w-8 h-8 mx-auto mb-2 opacity-50" />
                        <p className="text-sm">ダウンロード待機中のアイテムはありません</p>
                      </CardContent>
                    </Card>
                  ) : (
                    <div className="space-y-2">
                      {queue.map((item) => (
                        <Card key={item.id} className="bg-secondary/50">
                          <CardContent className="py-3">
                            <div className="flex items-center justify-between mb-2">
                              <span className="text-sm font-medium truncate">
                                {item.id}
                              </span>
                              <Badge
                                variant={
                                  item.status === 'completed' ? 'success' :
                                  item.status === 'failed' ? 'destructive' :
                                  item.status === 'processing' ? 'default' :
                                  'secondary'
                                }
                              >
                                {item.status === 'completed' && <CheckCircle className="w-3 h-3 mr-1" />}
                                {item.status === 'failed' && <AlertCircle className="w-3 h-3 mr-1" />}
                                {item.status === 'processing' && <Clock className="w-3 h-3 mr-1" />}
                                {item.status}
                              </Badge>
                            </div>
                            {item.status === 'processing' && (
                              <Progress value={item.progress} className="h-1" />
                            )}
                            <div className="flex justify-between text-xs text-muted-foreground mt-2">
                              <span>{item.estimatedSize.toFixed(1)} MB</span>
                              <span>{format(item.createdAt, 'HH:mm', { locale: ja })}</span>
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  )}
                </div>

                {/* Download Options */}
                <div className="space-y-2">
                  <Label>出力形式</Label>
                  <Select defaultValue="citygml">
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="citygml">CityGML</SelectItem>
                      <SelectItem value="geojson">GeoJSON</SelectItem>
                      <SelectItem value="shapefile">Shapefile</SelectItem>
                      <SelectItem value="3dtiles">
                        <div className="flex items-center gap-1">
                          3D Tiles
                          <Badge variant="secondary" className="text-xs">Pro</Badge>
                        </div>
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>座標系</Label>
                  <Select defaultValue="jgd2011">
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="jgd2011">JGD2011</SelectItem>
                      <SelectItem value="wgs84">WGS84</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <Button 
                  className="w-full"
                  disabled={selectedBuildings.size === 0}
                >
                  <Download className="w-4 h-4 mr-2" />
                  ダウンロード開始
                </Button>

                {/* Usage Stats */}
                <Card className="bg-primary/5 border-primary/20">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm">利用状況</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span>月間ダウンロード</span>
                        <span>12 / 100</span>
                      </div>
                      <Progress value={12} className="h-1" />
                    </div>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span>使用容量</span>
                        <span>2.4 GB / 10 GB</span>
                      </div>
                      <Progress value={24} className="h-1" />
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </div>
          </ScrollArea>
        </Tabs>
      </CardContent>
    </Card>
  );
}