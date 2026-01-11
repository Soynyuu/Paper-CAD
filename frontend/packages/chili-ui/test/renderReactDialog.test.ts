import React, { act } from "react";
import { renderReactDialog } from "../src/react/renderReactDialog";

test("renderReactDialog mounts above popovers and cleans up", async () => {
    (globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

    const Dialog = () => React.createElement("div", { "data-testid": "content" }, "hello");

    let cleanup: (() => void) | undefined;
    await act(async () => {
        cleanup = renderReactDialog(Dialog, {});
    });

    const content = document.querySelector('[data-testid="content"]') as HTMLElement | null;
    expect(content).not.toBeNull();

    const container = content!.parentElement as HTMLDivElement | null;
    expect(container).not.toBeNull();
    expect(container!.style.zIndex).toBe("var(--z-tooltip, 10001)");

    await act(async () => {
        cleanup?.();
    });
    expect(document.querySelector('[data-testid="content"]')).toBeNull();
});
