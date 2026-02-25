import * as SliderPrimitive from '@radix-ui/react-slider';

interface SliderProps {
  label?: string;
  min: number;
  max: number;
  step?: number;
  value: number[];
  onValueChange: (value: number[]) => void;
  formatValue?: (value: number) => string;
}

export function Slider({ label, min, max, step = 1, value, onValueChange, formatValue }: SliderProps) {
  const format = formatValue || ((v) => v.toLocaleString());
  
  return (
    <div className="space-y-3">
      {label && (
        <div className="flex justify-between items-center">
          <label className="block text-sm font-medium text-foreground">{label}</label>
          <span className="text-sm text-muted-foreground">
            {format(value[0])} - {format(value[1])}
          </span>
        </div>
      )}
      <SliderPrimitive.Root
        className="relative flex items-center select-none touch-none w-full h-5"
        value={value}
        onValueChange={onValueChange}
        min={min}
        max={max}
        step={step}
      >
        <SliderPrimitive.Track className="bg-secondary relative grow rounded-full h-1.5">
          <SliderPrimitive.Range className="absolute bg-primary rounded-full h-full" />
        </SliderPrimitive.Track>
        {value.map((_, i) => (
          <SliderPrimitive.Thumb
            key={i}
            className="block w-4 h-4 bg-primary rounded-full shadow-lg hover:scale-110 focus:outline-none focus:ring-2 focus:ring-ring transition-transform"
          />
        ))}
      </SliderPrimitive.Root>
    </div>
  );
}
