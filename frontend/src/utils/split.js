// Bill-splitting math. Everything is computed in integer minor units
// (rupiah, or cents for 2-decimal currencies) so shares always add up exactly.

export const UNASSIGNED = "__unassigned";

/**
 * Split an integer `total` across `weights` proportionally, using the
 * largest-remainder method so the parts sum to exactly `total`.
 * Falls back to an even split when all weights are zero.
 */
export function allocate(total, weights) {
    const count = weights.length;
    if (count === 0) return [];

    const weightSum = weights.reduce((a, b) => a + b, 0);
    const useWeights = weightSum > 0 ? weights : weights.map(() => 1);
    const useSum = weightSum > 0 ? weightSum : count;

    const exact = useWeights.map((weight) => (total * weight) / useSum);
    const parts = exact.map(Math.floor);
    const remainder = total - parts.reduce((a, b) => a + b, 0);

    const order = exact
        .map((value, index) => ({ index, fraction: value - Math.floor(value) }))
        .sort((a, b) => b.fraction - a.fraction || a.index - b.index);

    for (let k = 0; k < remainder; k++) {
        parts[order[k % count].index] += 1;
    }

    return parts;
}

/**
 * @param items    [{ id, total, assigned: [personId, ...] }] — `assigned` empty = nobody yet
 * @param people   [{ id }]
 * @param charges  { tax, service, discount, rounding } — amounts to add on top of the items
 * @param decimals 0 for IDR-style currencies, 2 otherwise
 * @returns { shares: [{ id, items, extras, total }], unassigned: {items, extras, total}, total }
 */
export function computeSplit({ items, people, charges, decimals }) {
    const factor = 10 ** decimals;
    const toMinor = (value) => Math.round((Number(value) || 0) * factor);

    const buckets = [...people.map((person) => person.id), UNASSIGNED];
    const itemMinor = Object.fromEntries(buckets.map((id) => [id, 0]));

    for (const item of items) {
        const amount = toMinor(item.total);

        if (!item.assigned || item.assigned.length === 0) {
            itemMinor[UNASSIGNED] += amount;
            continue;
        }

        allocate(amount, item.assigned.map(() => 1)).forEach((part, index) => {
            itemMinor[item.assigned[index]] += part;
        });
    }

    const extrasTotal =
        toMinor(charges.tax) +
        toMinor(charges.service) -
        toMinor(charges.discount) +
        toMinor(charges.rounding);

    // Tax, service, discounts and rounding follow each person's share of the items.
    let weights = buckets.map((id) => Math.max(itemMinor[id], 0));
    if (weights.every((weight) => weight === 0)) {
        weights = buckets.map((id) => (id === UNASSIGNED ? 0 : 1));
    }
    const extraParts = allocate(extrasTotal, weights);

    const build = (id, index) => {
        const itemsAmount = itemMinor[id];
        const extras = extraParts[index];
        return {
            id,
            items: itemsAmount / factor,
            extras: extras / factor,
            total: (itemsAmount + extras) / factor
        };
    };

    const rows = buckets.map(build);
    const unassigned = rows.pop();

    return {
        shares: rows,
        unassigned,
        total: rows.reduce((sum, row) => sum + row.total, unassigned.total)
    };
}
