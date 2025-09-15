'use client';

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { REGIONS } from '@/lib/constants';

interface RegionSelectorProps {
  value: string;
  onChange: (value: string) => void;
}

export function RegionSelector({ value, onChange }: RegionSelectorProps) {
  return (
    <div className="space-y-2">
      <Label htmlFor="region">地域選択</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger id="region" className="w-full">
          <SelectValue placeholder="地域を選択してください" />
        </SelectTrigger>
        <SelectContent>
          {REGIONS.map((region) => (
            <SelectItem key={region.id} value={region.id}>
              {region.prefecture} - {region.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}