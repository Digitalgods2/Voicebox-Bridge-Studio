import * as React from 'react';
import { cn } from '@/lib/utils/cn';

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        className={cn(
          'flex min-h-[80px] w-full rounded-md border border-input bg-[hsl(var(--field))] px-3 py-2 text-sm text-foreground ring-offset-background',
          'placeholder:text-[hsl(var(--placeholder))] focus-visible:outline-none focus-visible:border-accent/70 focus-visible:ring-2 focus-visible:ring-ring/40 focus-visible:ring-offset-0 disabled:cursor-not-allowed disabled:opacity-60',
          className,
        )}
        ref={ref}
        {...props}
      />
    );
  },
);
Textarea.displayName = 'Textarea';

export { Textarea };
