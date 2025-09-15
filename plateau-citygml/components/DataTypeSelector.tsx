'use client';

import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { DATA_TYPES } from '@/lib/constants';

interface DataTypeSelectorProps {
  selectedTypes: string[];
  onChange: (types: string[]) => void;
}

export function DataTypeSelector({ selectedTypes, onChange }: DataTypeSelectorProps) {
  const handleToggle = (typeId: string) => {
    if (selectedTypes.includes(typeId)) {
      onChange(selectedTypes.filter(id => id !== typeId));
    } else {
      onChange([...selectedTypes, typeId]);
    }
  };

  return (
    <div className="space-y-3">
      <Label>データタイプ</Label>
      <div className="space-y-2">
        {DATA_TYPES.map((type) => (
          <div key={type.id} className="flex items-start space-x-2">
            <Checkbox
              id={type.id}
              checked={selectedTypes.includes(type.id)}
              onCheckedChange={() => handleToggle(type.id)}
            />
            <div className="flex-1">
              <Label htmlFor={type.id} className="text-sm font-medium cursor-pointer">
                {type.name}
              </Label>
              <p className="text-xs text-muted-foreground">{type.description}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}