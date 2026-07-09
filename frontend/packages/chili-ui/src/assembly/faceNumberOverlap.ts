export interface FaceNumberLabelRect {
    faceNumber: number;
    rect: Pick<DOMRect, "bottom" | "height" | "left" | "right" | "top" | "width">;
}

export function detectOverlappingFaceNumberGroups(
    labels: FaceNumberLabelRect[],
    tolerance: number = 2,
): number[][] {
    const visibleLabels = labels.filter(({ faceNumber, rect }) => {
        return !Number.isNaN(faceNumber) && rect.width > 0 && rect.height > 0;
    });

    const parent = new Map<number, number>();
    visibleLabels.forEach((_, index) => parent.set(index, index));

    const find = (index: number): number => {
        const current = parent.get(index) ?? index;
        if (current === index) return index;
        const root = find(current);
        parent.set(index, root);
        return root;
    };

    const union = (a: number, b: number) => {
        const rootA = find(a);
        const rootB = find(b);
        if (rootA !== rootB) {
            parent.set(rootB, rootA);
        }
    };

    for (let i = 0; i < visibleLabels.length; i++) {
        for (let j = i + 1; j < visibleLabels.length; j++) {
            if (rectsOverlap(visibleLabels[i].rect, visibleLabels[j].rect, tolerance)) {
                union(i, j);
            }
        }
    }

    const groups = new Map<number, Set<number>>();
    visibleLabels.forEach(({ faceNumber }, index) => {
        const root = find(index);
        const group = groups.get(root) ?? new Set<number>();
        group.add(faceNumber);
        groups.set(root, group);
    });

    return Array.from(groups.values())
        .map((group) => Array.from(group).sort((a, b) => a - b))
        .filter((faceNumbers) => faceNumbers.length > 1)
        .sort((a, b) => a[0] - b[0]);
}

function rectsOverlap(
    a: FaceNumberLabelRect["rect"],
    b: FaceNumberLabelRect["rect"],
    tolerance: number = 0,
): boolean {
    return !(
        a.right <= b.left + tolerance ||
        b.right <= a.left + tolerance ||
        a.bottom <= b.top + tolerance ||
        b.bottom <= a.top + tolerance
    );
}
