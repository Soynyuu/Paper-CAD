'use client';

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { LOD_LEVELS } from '@/lib/constants';

interface LODSelectorProps {
  value: string;
  onChange: (value: string) => void;
}

export function LODSelector({ value, onChange }: LODSelectorProps) {
  return (
    <div className="space-y-2">
      <Label htmlFor="lod">詳細度（LOD）</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger id="lod" className="w-full">
          <SelectValue placeholder="詳細度を選択" />
        </SelectTrigger>
        <SelectContent>
          {LOD_LEVELS.map((lod) => (
            <SelectItem key={lod.level} value={lod.level}>
              <div>
                <div className="font-medium">{lod.level}</div>
                <div className="text-xs text-muted-foreground">
                  {lod.description} - {lod.estimatedSize}
                </div>
              </div>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}