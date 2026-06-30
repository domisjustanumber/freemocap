export function formatApplyErrorDetail(body: unknown, status: number): string {
    if (body && typeof body === 'object' && 'detail' in body) {
        const {detail} = body as { detail?: unknown };
        if (typeof detail === 'string') return detail;
        if (Array.isArray(detail)) {
            const parts = detail
                .map((item) =>
                    item && typeof item === 'object' && 'msg' in item
                        ? String((item as { msg: unknown }).msg)
                        : null,
                )
                .filter(Boolean);
            if (parts.length) return parts.join('; ');
        }
    }
    return `Failed to apply realtime (${status})`;
}
