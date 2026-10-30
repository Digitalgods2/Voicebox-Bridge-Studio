import * as SliderPrimitive from '@radix-ui/react-slider';
import * as React from 'react';
import { cn } from '@/lib/utils/cn';

const Slider = React.forwardRef<
  React.ElementRef<typeof SliderPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root>
>(({ className, ...props }, ref) => (
  <SliderPrimitive.Root
    ref={ref}
    className={cn('relative flex w-full touch-none select-none items-center', className)}
    {...props}
  >
    <SliderPrimitive.Track className="relative h-2 w-full grow overflow-hidden rounded-full bg-muted shadow-[inset_0_1px_2px_rgba(0,0,0,0.6)]">
      <SliderPrimitive.Range className="absolute h-full gold-fill" />
    </SliderPrimitive.Track>
    <SliderPrimitive.Thumb className="block h-0 w-0 outline-none disabled:pointer-events-none disabled:opacity-50 after:block after:h-5 after:w-5 after:rounded-full after:border-2 after:border-primary after:bg-foreground after:shadow-[0_0_10px_rgba(214,167,79,0.45)] after:ring-offset-background after:transition-colors after:absolute after:top-1/2 after:left-1/2 after:-translate-x-1/2 after:-translate-y-1/2 focus-visible:after:ring-2 focus-visible:after:ring-ring focus-visible:after:ring-offset-2" />
  </SliderPrimitive.Root>
));
Slider.displayName = SliderPrimitive.Root.displayName;

export { Slider };
