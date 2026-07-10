import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../lib/utils";

const buttonVariants = cva(
    "inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-md border font-sans text-sm font-medium leading-none transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-0 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
    {
        variants: {
            variant: {
                default:
                    "border-primary bg-primary text-primary-foreground hover:bg-[var(--primary-dark,var(--primary-color))]",
                secondary:
                    "border-border bg-secondary text-secondary-foreground hover:bg-accent hover:text-accent-foreground",
                outline:
                    "border-border bg-background text-foreground hover:bg-accent hover:text-accent-foreground",
                ghost: "border-transparent bg-transparent text-foreground hover:bg-accent hover:text-accent-foreground",
                destructive:
                    "border-destructive bg-transparent text-destructive hover:bg-[color-mix(in_srgb,var(--danger-color,#e74c3c)_10%,transparent_90%)]",
            },
            size: {
                default: "h-9 px-3",
                sm: "h-8 px-2.5 text-xs",
                lg: "h-10 px-4",
                icon: "size-8 p-0",
            },
        },
        defaultVariants: {
            variant: "default",
            size: "default",
        },
    },
);

export interface ButtonProps
    extends React.ButtonHTMLAttributes<HTMLButtonElement>,
        VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
    ({ className, variant, size, ...props }, ref) => {
        return <button className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
    },
);
Button.displayName = "Button";

export { Button, buttonVariants };
