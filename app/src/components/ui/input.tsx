import * as React from 'react';
import { cn } from '@/lib/utils/cn';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          'flex h-10 w-full rounded-md border border-input bg-[hsl(var(--field))] px-3 py-2 text-sm text-foreground ring-offset-background',
          'file:mr-3 file:rounded-full file:border file:border-accent/50 file:bg-accent/10 file:px-3 file:py-0.5 file:text-sm file:font-medium file:text-accent hover:file:bg-accent/20',
          'placeholder:text-[hsl(var(--placeholder))] focus-visible:outline-none focus-visible:border-accent/70 focus-visible:ring-2 focus-visible:ring-ring/40 focus-visible:ring-offset-0 disabled:cursor-not-allowed disabled:opacity-60',
          className,
        )}
        ref={ref}
        {...props}
      />
    );
  },
);
Input.displayName = 'Input';

export { Input };
