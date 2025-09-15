'use client';

import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ControlPanel } from '@/components/dashboard/ControlPanel';
import { PlateauService } from '@/lib/services/plateau-service';
import { PlateauDataset } from '@/types';
import { useAppStore } from '@/lib/store/app-store';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Badge } from '@/components/ui/badge';
import { 
  Settings, LogOut, User, CreditCard, HelpCircle, 
  FileText, Shield, Zap, Menu, X
} from 'lucide-react';

// Dynamically import MapboxViewer to avoid SSR issues
const MapViewer = dynamic(
  () => import('@/components/map/MapboxViewer').then(mod => ({ default: mod.MapboxViewer })),
  { 
    ssr: false,
    loading: () => (
      <div className="w-full h-full bg-gray-900 flex items-center justify-center">
        <div className="text-white">
          <div className="animate-pulse flex flex-col items-center">
            <div className="w-16 h-16 bg-blue-500 rounded-full animate-bounce mb-4"></div>
            <p className="text-lg">3Dマップを読み込み中...</p>
          </div>
        </div>
      </div>
    )
  }
);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      gcTime: 1000 * 60 * 10, // 10 minutes
    },
  },
});

export default function PlatformPage() {
  const [datasets, setDatasets] = useState<PlateauDataset[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const selectedRegion = useAppStore(state => state.selectedRegion);

  useEffect(() => {
    const loadDatasets = async () => {
      if (!selectedRegion) {
        setDatasets([]);
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      try {
        const plateauService = PlateauService.getInstance();
        const data = await plateauService.getDatasets(selectedRegion.prefecture, selectedRegion.name);
        
        // Get 3D Tiles URLs for datasets
        const datasetsWithTiles = await Promise.all(
          data.slice(0, 3).map(async (dataset) => { // Limit to 3 for performance
            const tilesetUrl = await plateauService.get3DTilesUrl(dataset.id);
            return { ...dataset, tilesetUrl: tilesetUrl || undefined };
          })
        );
        
        setDatasets(datasetsWithTiles);
      } catch (error) {
        console.error('Failed to load datasets:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadDatasets();
  }, [selectedRegion]);

  return (
    <QueryClientProvider client={queryClient}>
      <div className="h-screen flex flex-col bg-background">
        {/* Header */}
        <header className="bg-background border-b h-16 flex items-center justify-between px-4 lg:px-6">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              onClick={() => setSidebarOpen(!sidebarOpen)}
            >
              {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </Button>
            
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-sm">P</span>
              </div>
              <div>
                <h1 className="text-lg font-bold">PLATEAU Platform</h1>
                <p className="text-xs text-muted-foreground">Professional 3D City Model Service</p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <Badge variant="outline" className="hidden sm:flex items-center gap-1">
              <Zap className="w-3 h-3" />
              Pro Plan
            </Badge>
            
            <Button variant="ghost" size="icon">
              <HelpCircle className="h-5 w-5" />
            </Button>
            
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="relative h-10 w-10 rounded-full">
                  <Avatar className="h-10 w-10">
                    <AvatarImage src="/avatar.png" alt="User" />
                    <AvatarFallback>JP</AvatarFallback>
                  </Avatar>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent className="w-56" align="end" forceMount>
                <DropdownMenuLabel className="font-normal">
                  <div className="flex flex-col space-y-1">
                    <p className="text-sm font-medium leading-none">山田 太郎</p>
                    <p className="text-xs leading-none text-muted-foreground">
                      yamada@example.com
                    </p>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem>
                  <User className="mr-2 h-4 w-4" />
                  <span>プロフィール</span>
                </DropdownMenuItem>
                <DropdownMenuItem>
                  <CreditCard className="mr-2 h-4 w-4" />
                  <span>プラン・料金</span>
                </DropdownMenuItem>
                <DropdownMenuItem>
                  <Settings className="mr-2 h-4 w-4" />
                  <span>設定</span>
                </DropdownMenuItem>
                <DropdownMenuItem>
                  <Shield className="mr-2 h-4 w-4" />
                  <span>APIキー</span>
                </DropdownMenuItem>
                <DropdownMenuItem>
                  <FileText className="mr-2 h-4 w-4" />
                  <span>ドキュメント</span>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem className="text-red-600">
                  <LogOut className="mr-2 h-4 w-4" />
                  <span>ログアウト</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        {/* Main Content */}
        <div className="flex-1 flex overflow-hidden">
          {/* Sidebar */}
          <aside className={`
            ${sidebarOpen ? 'w-80' : 'w-0'}
            transition-all duration-300 ease-in-out
            border-r bg-background overflow-hidden
            lg:w-80
          `}>
            <div className="h-full w-80">
              <ControlPanel />
            </div>
          </aside>

          {/* Map View */}
          <main className="flex-1 relative">
            <MapViewer
              onBuildingSelect={(buildingId) => {
                console.log('Building selected:', buildingId);
              }}
              onAreaSelect={(bbox) => {
                console.log('Area selected:', bbox);
              }}
            />
            
            {/* Floating Stats */}
            <div className="absolute top-4 left-4 bg-background/95 backdrop-blur rounded-lg shadow-lg p-4 space-y-2">
              <div className="text-sm">
                <span className="text-muted-foreground">選択地域: </span>
                <span className="font-medium">
                  {selectedRegion ? `${selectedRegion.prefecture} ${selectedRegion.name}` : '未選択'}
                </span>
              </div>
              <div className="text-sm">
                <span className="text-muted-foreground">データセット: </span>
                <span className="font-medium">{datasets.length} 件</span>
              </div>
              <div className="text-sm">
                <span className="text-muted-foreground">選択建物: </span>
                <span className="font-medium">
                  {useAppStore.getState().selectedBuildings.size.toLocaleString()} 棟
                </span>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="absolute bottom-4 right-4 flex flex-col gap-2">
              <Button size="lg" className="shadow-lg">
                <Zap className="w-4 h-4 mr-2" />
                クイックエクスポート
              </Button>
            </div>
          </main>
        </div>
      </div>
    </QueryClientProvider>
  );
}