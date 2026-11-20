import { useMemo, useState } from "react";
import { decimalsFor, formatMoney } from "../utils/money";
import { computeSplit } from "../utils/split";

// One colour per person so their orders and totals are easy to match up.
const COLORS = [
    "#1f5a43", "#2f5f9e", "#a8501f", "#7a3f8f",
    "#8a6d00", "#2c7a7b", "#a8322b", "#4f5d75"
];

let nextPersonId = 0;
const newPerson = (name) => ({ id: `p${nextPersonId}`, name, color: COLORS[nextPersonId++ % COLORS.length] });

// The page reads top to bottom: 1. who is splitting, 2. what each person ordered, 3. what everyone pays.
function SplitBill({ merchant, date, currency, items, charges, onBack }) {
    const [people, setPeople] = useState(() => [newPerson("Person 1"), newPerson("Person 2")]);
    // itemId -> [personId]. An item nobody picked is "unassigned".
    const [assignments, setAssignments] = useState({});
    const [copied, setCopied] = useState(false);

    const money = (value) => formatMoney(value, currency);
    const nameOf = (person) => person.name.trim() || "Unnamed";

    const split = useMemo(() => {
        const ids = people.map((person) => person.id);

        return computeSplit({
            items: items.map((item) => ({
                id: item.id,
                total: item.total,
                assigned: (assignments[item.id] ?? []).filter((id) => ids.includes(id))
            })),
            people: ids.map((id) => ({ id })),
            charges,
            decimals: decimalsFor(currency)
        });
    }, [items, people, assignments, charges, currency]);

    const holders = (itemId) => {
        const ids = assignments[itemId] ?? [];
        return people.filter((person) => ids.includes(person.id));
    };

    const unassignedItems = items.filter((item) => holders(item.id).length === 0);
    const assignedCount = items.length - unassignedItems.length;

    function addPerson() {
        setPeople((current) => [...current, newPerson(`Person ${current.length + 1}`)]);
    }

    function renamePerson(id, name) {
        setPeople((current) => current.map((p) => (p.id === id ? { ...p, name } : p)));
    }

    function removePerson(id) {
        setPeople((current) => current.filter((p) => p.id !== id));
    }

    function toggle(personId, itemId) {
        setAssignments((all) => {
            const current = all[itemId] ?? [];
            const next = current.includes(personId)
                ? current.filter((id) => id !== personId)
                : [...current, personId];
            return { ...all, [itemId]: next };
        });
    }

    function setAllFor(personId, selected) {
        setAssignments((all) => {
            const next = { ...all };
            for (const item of items) {
                const current = (all[item.id] ?? []).filter((id) => id !== personId);
                next[item.id] = selected ? [...current, personId] : current;
            }
            return next;
        });
    }

    function shareUnassigned() {
        const everyone = people.map((person) => person.id);
        setAssignments((all) => {
            const next = { ...all };
            for (const item of unassignedItems) next[item.id] = everyone;
            return next;
        });
    }

    async function copySummary() {
        const heading = [merchant, date].filter(Boolean).join(" · ") || "Bill split";
        const lines = split.shares.map((share, index) => `${nameOf(people[index])}: ${money(share.total)}`);

        try {
            await navigator.clipboard.writeText([heading, ...lines].join("\n"));
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch {
            // Clipboard can be blocked (e.g. insecure context); the totals stay on screen.
        }
    }

    const extrasTotal = charges.tax + charges.service - charges.discount + charges.rounding;
    const itemName = (id) => items.find((item) => item.id === id)?.name ?? "";

    return (
        <div className="split">
            <div className="page-head">
                <div>
                    <h1>Split the bill</h1>
                    <p className="lead">
                        Add everyone, then mark what each person ordered.
                    </p>
                </div>
                <button className="button secondary" type="button" onClick={onBack}>
                    ← Edit receipt
                </button>
            </div>

            {/* 1 — people */}
            <section className="card flow-step" aria-labelledby="step-people">
                <h2 id="step-people">
                    <span className="step-badge">1</span> Who's splitting?
                </h2>

                <ul className="people-list">
                    {people.map((person, index) => (
                        <li key={person.id}>
                            <span className="dot" style={{ background: person.color }} aria-hidden="true" />
                            <input
                                type="text"
                                value={person.name}
                                onChange={(e) => renamePerson(person.id, e.target.value)}
                                aria-label={`Name of person ${index + 1}`}
                            />
                            <button
                                type="button"
                                className="icon-button"
                                onClick={() => removePerson(person.id)}
                                disabled={people.length <= 1}
                                aria-label={`Remove ${nameOf(person)}`}
                            >
                                ×
                            </button>
                        </li>
                    ))}
                </ul>

                <button type="button" className="button secondary full" onClick={addPerson}>
                    + Add person
                </button>
            </section>

            {/* 2 — what each person ordered */}
            <section className="flow-step" aria-labelledby="step-orders">
                <div className="step-title">
                    <h2 id="step-orders">
                        <span className="step-badge">2</span> What did each person order?
                    </h2>
                    <p className="hint">
                        Tap an item to add it to that person. If two people tap the same item, they split it equally.
                    </p>
                </div>

                <div className="coverage" role="status">
                    <div className="coverage-bar" aria-hidden="true">
                        <span style={{ width: items.length ? `${(assignedCount / items.length) * 100}%` : "0%" }} />
                    </div>
                    <span>
                        {assignedCount} of {items.length} items assigned
                    </span>
                    {unassignedItems.length > 0 && people.length > 1 && (
                        <button type="button" className="link-button" onClick={shareUnassigned}>
                            Share the rest equally
                        </button>
                    )}
                </div>

                {people.map((person, index) => {
                    const share = split.shares[index];
                    const picked = split.itemShares[person.id].length;

                    return (
                        <div className="card person-card" key={person.id} style={{ "--person": person.color }}>
                            <div className="person-head">
                                <span className="dot" style={{ background: person.color }} aria-hidden="true" />
                                <div className="grow">
                                    <h3>{nameOf(person)}</h3>
                                    <span className="hint">
                                        {picked === 0 ? "Nothing picked yet" : `${picked} item${picked > 1 ? "s" : ""} · ${money(share.items)}`}
                                    </span>
                                </div>
                                <div className="person-actions">
                                    <button type="button" className="link-button" onClick={() => setAllFor(person.id, true)}>
                                        All
                                    </button>
                                    <button type="button" className="link-button" onClick={() => setAllFor(person.id, false)}>
                                        None
                                    </button>
                                </div>
                            </div>

                            <ul className="order-list">
                                {items.map((item) => {
                                    const who = holders(item.id);
                                    const mine = who.some((p) => p.id === person.id);
                                    const others = who.filter((p) => p.id !== person.id);

                                    return (
                                        <li key={item.id}>
                                            <button
                                                type="button"
                                                className={`order-row ${mine ? "on" : ""}`}
                                                aria-pressed={mine}
                                                onClick={() => toggle(person.id, item.id)}
                                            >
                                                <span className="tick" aria-hidden="true">{mine ? "✓" : ""}</span>
                                                <span className="order-name">
                                                    {item.name}
                                                    {others.length > 0 && (
                                                        <small>
                                                            {mine ? "shared with " : "also "}
                                                            {others.map(nameOf).join(", ")}
                                                        </small>
                                                    )}
                                                </span>
                                                <span className="order-price">
                                                    {money(mine && who.length > 1 ? item.total / who.length : item.total)}
                                                </span>
                                            </button>
                                        </li>
                                    );
                                })}
                            </ul>
                        </div>
                    );
                })}
            </section>

            {/* 3 — totals */}
            <section className="flow-step" aria-labelledby="step-totals">
                <div className="step-title">
                    <h2 id="step-totals">
                        <span className="step-badge">3</span> Everyone's share
                    </h2>
                </div>

                {unassignedItems.length > 0 && (
                    <p className="notice warn">
                        {unassignedItems.length === 1 ? "1 item isn't" : `${unassignedItems.length} items aren't`} assigned
                        to anyone yet ({money(split.unassigned.items)}). Go back up and tap who ordered
                        {unassignedItems.length === 1 ? " it" : " them"}.
                    </p>
                )}

                <div className="card results">
                    <ul className="results-list">
                        {split.shares.map((share, index) => {
                            const person = people[index];
                            const lines = split.itemShares[person.id];

                            return (
                                <li key={person.id}>
                                    <details>
                                        <summary>
                                            <span className="dot" style={{ background: person.color }} aria-hidden="true" />
                                            <strong className="grow">{nameOf(person)}</strong>
                                            <strong className="amount-due">{money(share.total)}</strong>
                                        </summary>

                                        <ul className="breakdown">
                                            {lines.length === 0 && <li className="hint">No items picked.</li>}
                                            {lines.map((line) => (
                                                <li key={line.id}>
                                                    <span>{itemName(line.id)}</span>
                                                    <span>{money(line.amount)}</span>
                                                </li>
                                            ))}
                                            {share.extras !== 0 && (
                                                <li>
                                                    <span>Tax, fees &amp; adjustments</span>
                                                    <span>
                                                        {share.extras < 0 ? "−" : ""}
                                                        {money(Math.abs(share.extras))}
                                                    </span>
                                                </li>
                                            )}
                                        </ul>
                                    </details>
                                </li>
                            );
                        })}
                    </ul>

                    <div className="summary-total">
                        <span>
                            Bill total
                            {extrasTotal !== 0 && (
                                <small> includes {money(extrasTotal)} tax, fees and adjustments</small>
                            )}
                        </span>
                        <strong>{money(split.total)}</strong>
                    </div>

                    <button type="button" className="button primary full" onClick={copySummary}>
                        {copied ? "Copied" : "Copy summary"}
                    </button>
                </div>
            </section>
        </div>
    );
}

export default SplitBill;
