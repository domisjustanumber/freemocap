export function areSortedCameraIdSetsEqual(a: readonly string[], b: readonly string[]): boolean {
    if (a.length !== b.length) return false;
    return a.every((id, index) => id === b[index]);
}

export function sortCameraIds(ids: Iterable<string>): string[] {
    return [...ids].sort();
}
