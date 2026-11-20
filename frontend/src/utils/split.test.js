import test from "node:test";
import assert from "node:assert/strict";
import { allocate, computeSplit, UNASSIGNED } from "./split.js";

const sum = (list) => list.reduce((a, b) => a + b, 0);
const none = { tax: 0, service: 0, discount: 0, rounding: 0 };
const people = (...ids) => ids.map((id) => ({ id }));

test("allocate always sums to the total", () => {
    assert.deepEqual(allocate(100, [1, 1, 1]), [34, 33, 33]);
    assert.equal(sum(allocate(10001, [3, 7, 11, 2])), 10001);
    assert.equal(sum(allocate(-501, [1, 2, 3])), -501);
    assert.deepEqual(allocate(5, [0, 0]), [3, 2]);
    assert.deepEqual(allocate(5, []), []);
});

test("shared item is split evenly", () => {
    const result = computeSplit({
        items: [{ id: 1, total: 90000, assigned: ["a", "b", "c"] }],
        people: people("a", "b", "c"),
        charges: none,
        decimals: 0
    });
    assert.deepEqual(result.shares.map((s) => s.total), [30000, 30000, 30000]);
});

test("tax and service follow each person's share of the items", () => {
    const result = computeSplit({
        items: [
            { id: 1, total: 60000, assigned: ["a"] },
            { id: 2, total: 20000, assigned: ["b"] }
        ],
        people: people("a", "b"),
        charges: { tax: 8000, service: 0, discount: 0, rounding: 0 },
        decimals: 0
    });
    assert.deepEqual(result.shares.map((s) => s.extras), [6000, 2000]);
    assert.deepEqual(result.shares.map((s) => s.total), [66000, 22000]);
    assert.equal(result.total, 88000);
});

test("discount reduces shares proportionally", () => {
    const result = computeSplit({
        items: [
            { id: 1, total: 30000, assigned: ["a"] },
            { id: 2, total: 10000, assigned: ["b"] }
        ],
        people: people("a", "b"),
        charges: { ...none, discount: 4000 },
        decimals: 0
    });
    assert.deepEqual(result.shares.map((s) => s.total), [27000, 9000]);
});

test("shares add up exactly even when amounts don't divide", () => {
    const result = computeSplit({
        items: [{ id: 1, total: 100000, assigned: ["a", "b", "c"] }],
        people: people("a", "b", "c"),
        charges: { tax: 11000, service: 5000, discount: 0, rounding: -1 },
        decimals: 0
    });
    assert.equal(result.total, 100000 + 11000 + 5000 - 1);
    assert.equal(sum(result.shares.map((s) => s.total)), result.total);
});

test("two-decimal currencies split in cents", () => {
    const result = computeSplit({
        items: [{ id: 1, total: 10, assigned: ["a", "b", "c"] }],
        people: people("a", "b", "c"),
        charges: { ...none, tax: 0.8 },
        decimals: 2
    });
    assert.equal(Math.round(result.total * 100), 1080);
    assert.equal(Math.round(sum(result.shares.map((s) => s.total)) * 100), 1080);
});

test("unassigned items are reported, not silently dropped", () => {
    const result = computeSplit({
        items: [
            { id: 1, total: 50000, assigned: ["a"] },
            { id: 2, total: 25000, assigned: [] }
        ],
        people: people("a"),
        charges: none,
        decimals: 0
    });
    assert.equal(result.unassigned.id, UNASSIGNED);
    assert.equal(result.unassigned.total, 25000);
    assert.equal(result.total, 75000);
});

test("no people yields no shares", () => {
    const result = computeSplit({
        items: [{ id: 1, total: 100, assigned: [] }],
        people: [],
        charges: none,
        decimals: 0
    });
    assert.deepEqual(result.shares, []);
    assert.equal(result.unassigned.total, 100);
});

test("per-item shares add up to each person's item total", () => {
    const result = computeSplit({
        items: [
            { id: 1, total: 100, assigned: ["a", "b", "c"] },
            { id: 2, total: 50, assigned: ["a"] }
        ],
        people: people("a", "b", "c"),
        charges: none,
        decimals: 0
    });

    for (const share of result.shares) {
        assert.equal(sum(result.itemShares[share.id].map((line) => line.amount)), share.items);
    }
    assert.deepEqual(result.itemShares.a.map((line) => line.id), [1, 2]);
    assert.deepEqual(result.itemShares.b.map((line) => line.id), [1]);
});
