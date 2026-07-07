import * as React from "react";
import { ScrollArea as BaseScrollArea } from "@base-ui/react/scroll-area";
import { cn } from "../../lib/utils";

const ScrollArea = React.forwardRef<
    HTMLDivElement,
    React.ComponentPropsWithoutRef<typeof BaseScrollArea.Root>
>(({ className, children, ...props }, ref) => (
    <BaseScrollArea.Root ref={ref} className={cn("relative overflow-hidden", className)} {...props}>
        {children}
    </BaseScrollArea.Root>
));
ScrollArea.displayName = "ScrollArea";

const ScrollAreaViewport = React.forwardRef<
    HTMLDivElement,
    React.ComponentPropsWithoutRef<typeof BaseScrollArea.Viewport>
>(({ className, ...props }, ref) => (
    <BaseScrollArea.Viewport ref={ref} className={cn("h-full w-full", className)} {...props} />
));
ScrollAreaViewport.displayName = "ScrollAreaViewport";

const ScrollAreaContent = React.forwardRef<
    HTMLDivElement,
    React.ComponentPropsWithoutRef<typeof BaseScrollArea.Content>
>(({ className, ...props }, ref) => (
    <BaseScrollArea.Content ref={ref} className={className} {...props} />
));
ScrollAreaContent.displayName = "ScrollAreaContent";

const ScrollBar = React.forwardRef<
    HTMLDivElement,
    React.ComponentPropsWithoutRef<typeof BaseScrollArea.Scrollbar>
>(({ className, ...props }, ref) => (
    <BaseScrollArea.Scrollbar ref={ref} className={className} {...props} />
));
ScrollBar.displayName = "ScrollBar";

const ScrollAreaThumb = React.forwardRef<
    HTMLDivElement,
    React.ComponentPropsWithoutRef<typeof BaseScrollArea.Thumb>
>(({ className, ...props }, ref) => (
    <BaseScrollArea.Thumb ref={ref} className={className} {...props} />
));
ScrollAreaThumb.displayName = "ScrollAreaThumb";

export { ScrollArea, ScrollAreaViewport, ScrollAreaContent, ScrollBar, ScrollAreaThumb };
