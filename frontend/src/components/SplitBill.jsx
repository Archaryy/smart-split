import { useMemo, useState } from "react";
import { decimalsFor, formatMoney } from "../utils/money";
import { computeSplit } from "../utils/split";

// One colour per person so chips and result rows are easy to match up.
const COLORS = [
    "#1f5a43", "#2f5f9e", "#a8501f", "#7a3f8f",
    "#8a6d00", "#2c7a7b", "#a8322b", "#4f5d75"
];

let nextPersonId = 0;
const newPerson = (name) => ({ id: `p${nextPersonId}`, name, color: COLORS[nextPersonId++ % COLORS.length] });

function SplitBill({ merchant, date, currency, items, charges, onBack }) {
    const [people, setPeople] = useState(() => [newPerson("Person 1"), newPerson("Person 2")]);
    // Only items someone changed are stored; everything else is shared by everyone.
    const [assignments, setAssignments] = useState({});
    const [copied, setCopied] = useState(false);

    const money = (value) => formatMoney(value, currency);
    const personIds = people.map((person) => person.id);
    const nameOf = (person) => person.name.trim() || "Unnamed";

    const assignedTo = (itemId) =>
        (assignments[itemId] ?? personIds).filter((id) => personIds.includes(id));

    const split = useMemo(() => {
        const ids = people.map((person) => person.id);

        return computeSplit({
            items: items.map((item) => ({
                id: item.id,
                total: item.total,
                assigned: (assignments[item.id] ?? ids).filter((id) => ids.includes(id))
            })),
            people: ids.map((id) => ({ id })),
            charges,
            decimals: decimalsFor(currency)
        });
    }, [items, people, assignments, charges, currency]);

    function addPerson() {
        setPeople((current) => [...current, newPerson(`Person ${current.length + 1}`)]);
    }

    function renamePerson(id, name) {
        setPeople((current) => current.map((p) => (p.id === id ? { ...p, name } : p)));
    }

    function removePerson(id) {
        setPeople((current) => current.filter((p) => p.id !== id));
    }

    function toggle(itemId, personId) {
        const current = assignedTo(itemId);
        const next = current.includes(personId)
            ? current.filter((id) => id !== personId)
            : [...current, personId];

        setAssignments((all) => ({ ...all, [itemId]: next }));
    }

    function shareWithEveryone(itemId) {
        setAssignments(({ [itemId]: _removed, ...rest }) => rest);
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

    const hasUnassigned = split.unassigned.total !== 0;
    const extrasTotal = charges.tax + charges.service - charges.discount + charges.rounding;

    return (
        <div className="split">
            <div className="review-head">
                <div>
                    <h1>Split the bill</h1>
                    <p className="lead">
                        Everyone shares each item by default. Tap names to change who had what.
                    </p>
                </div>
                <button className="button secondary" type="button" onClick={onBack}>
                    ← Edit receipt
                </button>
            </div>

            <div className="split-grid">
                <div className="split-left">
                    <div className="card">
                        <div className="card-title">
                            <h2>People</h2>
                            <span>{people.length}</span>
                        </div>

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

                        <button type="button" className="link-button add" onClick={addPerson}>
                            + Add person
                        </button>
                    </div>

                    <div className="card">
                        <div className="card-title">
                            <h2>Who had what</h2>
                            <span>{items.length} items</span>
                        </div>

                        <ul className="split-items">
                            {items.map((item) => {
                                const assigned = assignedTo(item.id);
                                const everyone = assigned.length === people.length;

                                return (
                                    <li key={item.id} className="split-item">
                                        <div className="split-item-head">
                                            <span className="name">{item.name}</span>
                                            <strong>{money(item.total)}</strong>
                                        </div>

                                        <div className="chips" role="group" aria-label={`Who had ${item.name}`}>
                                            {people.map((person) => {
                                                const on = assigned.includes(person.id);
                                                return (
                                                    <button
                                                        key={person.id}
                                                        type="button"
                                                        className={`chip ${on ? "on" : ""}`}
                                                        style={on ? { background: person.color, borderColor: person.color } : undefined}
                                                        aria-pressed={on}
                                                        onClick={() => toggle(item.id, person.id)}
                                                    >
                                                        {nameOf(person)}
                                                    </button>
                                                );
                                            })}

                                            {!everyone && (
                                                <button
                                                    type="button"
                                                    className="link-button"
                                                    onClick={() => shareWithEveryone(item.id)}
                                                >
                                                    Everyone
                                                </button>
                                            )}
                                        </div>

                                        {assigned.length === 0 ? (
                                            <p className="sub warn-text">Nobody is paying for this yet.</p>
                                        ) : assigned.length > 1 ? (
                                            <p className="sub">
                                                {money(item.total / assigned.length)} each
                                            </p>
                                        ) : null}
                                    </li>
                                );
                            })}
                        </ul>
                    </div>
                </div>

                <aside className="split-right">
                    <div className="card results">
                        <div className="card-title">
                            <h2>Each person pays</h2>
                        </div>

                        <ul className="results-list">
                            {split.shares.map((share, index) => {
                                const person = people[index];
                                return (
                                    <li key={person.id}>
                                        <span className="dot" style={{ background: person.color }} aria-hidden="true" />
                                        <div className="who">
                                            <strong>{nameOf(person)}</strong>
                                            <span>
                                                Items {money(share.items)}
                                                {share.extras !== 0 &&
                                                    ` ${share.extras > 0 ? "+" : "−"} ${money(Math.abs(share.extras))} tax & fees`}
                                            </span>
                                        </div>
                                        <strong className="amount-due">{money(share.total)}</strong>
                                    </li>
                                );
                            })}
                        </ul>

                        {hasUnassigned && (
                            <p className="notice warn">
                                {money(split.unassigned.total)} isn't assigned to anyone yet.
                            </p>
                        )}

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
                </aside>
            </div>
        </div>
    );
}

export default SplitBill;
