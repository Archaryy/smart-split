import { useMemo, useState } from "react";
import {
    CURRENCIES,
    formatMoney,
    roundMoney,
    sanitizeDecimal,
    toNumber
} from "../utils/money";
import SplitBill from "./SplitBill";

function toEditable(value) {
    return value ? String(value) : "";
}

// Stable row ids keep input focus when rows are added or removed.
let nextItemId = 0;
const makeId = () => nextItemId++;

function ReceiptReview({ receipt, ocr, imageUrl, onReset }) {
    const [merchant, setMerchant] = useState(receipt.merchant_name || "");
    const [date, setDate] = useState(receipt.transaction_date || "");
    const [currency, setCurrency] = useState(receipt.currency || "IDR");

    const [items, setItems] = useState(() =>
        (receipt.items || []).map((item) => ({
            id: makeId(),
            name: item.name,
            quantity: String(item.quantity ?? 1),
            unit: item.unit && item.unit !== "pcs" ? item.unit : "",
            total: String(item.total_price ?? 0),
            needsReview: Boolean(item.needs_review)
        }))
    );

    const [tax, setTax] = useState(toEditable(receipt.tax));
    const [taxIncluded, setTaxIncluded] = useState(Boolean(receipt.tax_included));
    const [service, setService] = useState(toEditable(receipt.service_charge));
    const [discount, setDiscount] = useState(toEditable(receipt.discount));
    const [rounding, setRounding] = useState(toEditable(receipt.rounding));
    const [stage, setStage] = useState("review"); // review | split
    // The split view stays mounted once opened so going back doesn't lose who had what.
    const [splitStarted, setSplitStarted] = useState(false);
    // On phones the photo would push the form off-screen, so start collapsed.
    const [photoOpen, setPhotoOpen] = useState(
        () => window.matchMedia("(min-width: 821px)").matches
    );

    const money = (value) => formatMoney(value, currency);
    const printedTotal = receipt.reconciliation?.printed_total;
    const printedSubtotal = receipt.reconciliation?.printed_subtotal;

    const totals = useMemo(() => {
        const subtotal = items.reduce((sum, item) => sum + toNumber(item.total), 0);
        const taxAmount = toNumber(tax);
        const adjustments =
            toNumber(service) - toNumber(discount) + toNumber(rounding);

        return {
            subtotal: roundMoney(subtotal),
            total: roundMoney(subtotal + (taxIncluded ? 0 : taxAmount) + adjustments)
        };
    }, [items, tax, taxIncluded, service, discount, rounding]);

    // Compare the edited receipt with what the receipt itself says.
    const check = useMemo(() => {
        const money = (value) => formatMoney(value, currency);
        const tolerance = Math.max(1, totals.total * 0.005);

        if (items.length === 0) {
            return { kind: "warn", title: "No items yet", detail: "Add the items from your receipt below." };
        }

        if (printedTotal != null) {
            const difference = roundMoney(totals.total - printedTotal);
            return Math.abs(difference) <= tolerance
                ? { kind: "ok", title: "Matches the receipt", detail: `Total ${money(printedTotal)} agrees with the printed total.` }
                : {
                    kind: "warn",
                    title: "Doesn't match the printed total",
                    detail: `Your items come to ${money(totals.total)}; the receipt says ${money(printedTotal)} (${difference > 0 ? "+" : "−"}${money(Math.abs(difference))}). Check for a missing or misread item.`
                };
        }

        if (printedSubtotal != null) {
            const difference = roundMoney(totals.subtotal - printedSubtotal);
            return Math.abs(difference) <= tolerance
                ? { kind: "ok", title: "Matches the receipt", detail: `Items add up to the printed subtotal of ${money(printedSubtotal)}.` }
                : {
                    kind: "warn",
                    title: "Doesn't match the printed subtotal",
                    detail: `Your items come to ${money(totals.subtotal)}; the receipt says ${money(printedSubtotal)}.`
                };
        }

        return {
            kind: "neutral",
            title: "No printed total to compare",
            detail: "Check the amounts against your receipt."
        };
    }, [items.length, totals, printedTotal, printedSubtotal, currency]);

    function updateItem(id, field, value) {
        // Editing a flagged line counts as having checked it.
        const clearsFlag = field === "name" || field === "total";

        setItems((current) =>
            current.map((item) =>
                item.id === id
                    ? {
                        ...item,
                        [field]: value,
                        needsReview: clearsFlag ? false : item.needsReview
                    }
                    : item
            )
        );
    }

    function addItem() {
        setItems((current) => [
            ...current,
            { id: makeId(), name: "", quantity: "1", unit: "", total: "", needsReview: false }
        ]);
    }

    function removeItem(id) {
        setItems((current) => current.filter((item) => item.id !== id));
    }

    const canConfirm =
        items.length > 0 &&
        items.every((item) => item.name.trim() && toNumber(item.quantity) > 0);

    const splitItems = useMemo(
        () =>
            items.map((item) => ({
                id: item.id,
                name: item.name.trim(),
                total: toNumber(item.total)
            })),
        [items]
    );

    const charges = useMemo(
        () => ({
            tax: taxIncluded ? 0 : toNumber(tax),
            service: toNumber(service),
            discount: toNumber(discount),
            rounding: toNumber(rounding)
        }),
        [tax, taxIncluded, service, discount, rounding]
    );

    function goTo(nextStage) {
        setStage(nextStage);
        window.scrollTo({ top: 0 });
    }

    return (
        <section className="review">
            {splitStarted && (
                <div hidden={stage !== "split"}>
                    <SplitBill
                        merchant={merchant}
                        date={date}
                        currency={currency}
                        items={splitItems}
                        charges={charges}
                        onBack={() => goTo("review")}
                    />
                </div>
            )}

            <div hidden={stage !== "review"}>
            <div className="review-head">
                <div>
                    <h1>Check the receipt</h1>
                    <p className="lead">Fix anything that was misread, then confirm.</p>
                </div>
                <button className="button secondary" type="button" onClick={onReset}>
                    Scan another
                </button>
            </div>

            <div className="review-grid">
                <aside className="receipt-photo">
                    <details
                        open={photoOpen}
                        onToggle={(e) => setPhotoOpen(e.currentTarget.open)}
                    >
                        <summary>Receipt photo</summary>
                        {imageUrl && <img src={imageUrl} alt="Uploaded receipt" />}
                    </details>
                </aside>

                <div className="review-main">
                    <div className={`check ${check.kind}`} role="status">
                        <span className="check-icon" aria-hidden="true">
                            {check.kind === "ok" ? "✓" : check.kind === "warn" ? "!" : "i"}
                        </span>
                        <div>
                            <strong>{check.title}</strong>
                            <p>{check.detail}</p>
                        </div>
                    </div>

                    {items.length === 0 && receipt.warnings?.length > 0 && (
                        <p className="notice warn">{receipt.warnings[0]}</p>
                    )}

                    <div className="card">
                        <div className="meta-fields">
                            <label className="field grow">
                                <span>Merchant</span>
                                <input
                                    type="text"
                                    value={merchant}
                                    onChange={(e) => setMerchant(e.target.value)}
                                    placeholder="Store or restaurant"
                                />
                            </label>

                            <label className="field">
                                <span>Date</span>
                                <input
                                    type="date"
                                    value={date}
                                    onChange={(e) => setDate(e.target.value)}
                                />
                            </label>

                            <label className="field">
                                <span>Currency</span>
                                <select
                                    value={currency}
                                    onChange={(e) => setCurrency(e.target.value)}
                                >
                                    {[...new Set([currency, ...CURRENCIES])].map((code) => (
                                        <option key={code} value={code}>
                                            {code}
                                        </option>
                                    ))}
                                </select>
                            </label>
                        </div>
                    </div>

                    <div className="card">
                        <div className="card-title">
                            <h2>Items</h2>
                            <span>{items.length}</span>
                        </div>

                        <div className="items-table" role="table" aria-label="Receipt items">
                            <div className="items-row items-labels" role="row">
                                <span role="columnheader">Item</span>
                                <span role="columnheader">Qty</span>
                                <span role="columnheader" className="right">Price</span>
                                <span role="columnheader" className="sr-only">Remove</span>
                            </div>

                            {items.map((item) => {
                                const quantity = toNumber(item.quantity);
                                const lineTotal = toNumber(item.total);
                                const showUnitPrice = quantity > 0 && quantity !== 1 && lineTotal > 0;

                                return (
                                    <div
                                        className={`items-row ${item.needsReview ? "needs-review" : ""}`}
                                        role="row"
                                        key={item.id}
                                    >
                                        <div className="name-cell" role="cell">
                                            <input
                                                type="text"
                                                value={item.name}
                                                onChange={(e) => updateItem(item.id, "name", e.target.value)}
                                                placeholder="Item name"
                                                aria-label="Item name"
                                            />
                                            {(showUnitPrice || item.unit || item.needsReview) && (
                                                <span className="sub">
                                                    {item.needsReview && <em>Check this line</em>}
                                                    {item.unit && <span>{item.unit}</span>}
                                                    {showUnitPrice && (
                                                        <span>{money(lineTotal / quantity)} each</span>
                                                    )}
                                                </span>
                                            )}
                                        </div>

                                        <label className="mini-field">
                                            <span className="mini-label">Qty</span>
                                            <input
                                                className="qty"
                                                type="text"
                                                inputMode="decimal"
                                                value={item.quantity}
                                                onChange={(e) =>
                                                    updateItem(item.id, "quantity", sanitizeDecimal(e.target.value))
                                                }
                                                aria-label={`Quantity for ${item.name || "item"}`}
                                            />
                                        </label>

                                        <label className="mini-field">
                                            <span className="mini-label">Price</span>
                                            <input
                                                className="price"
                                                type="text"
                                                inputMode="decimal"
                                                value={item.total}
                                                onChange={(e) =>
                                                    updateItem(item.id, "total", sanitizeDecimal(e.target.value))
                                                }
                                                placeholder="0"
                                                aria-label={`Price for ${item.name || "item"}`}
                                            />
                                        </label>

                                        <button
                                            type="button"
                                            className="icon-button"
                                            onClick={() => removeItem(item.id)}
                                            aria-label={`Remove ${item.name || "item"}`}
                                        >
                                            ×
                                        </button>
                                    </div>
                                );
                            })}
                        </div>

                        <button type="button" className="link-button add" onClick={addItem}>
                            + Add item
                        </button>
                    </div>

                    <div className="card summary">
                        <div className="summary-row">
                            <span>Subtotal</span>
                            <strong>{money(totals.subtotal)}</strong>
                        </div>

                        <div className="summary-row">
                            <div className="summary-label">
                                <label htmlFor="tax-amount">Tax</label>
                                <label className="inline-check">
                                    <input
                                        type="checkbox"
                                        checked={taxIncluded}
                                        onChange={(e) => setTaxIncluded(e.target.checked)}
                                    />
                                    already in prices
                                </label>
                            </div>
                            <input
                                id="tax-amount"
                                className="amount"
                                type="text"
                                inputMode="decimal"
                                value={tax}
                                onChange={(e) => setTax(sanitizeDecimal(e.target.value))}
                                placeholder="0"
                            />
                        </div>

                        <div className="summary-row">
                            <label htmlFor="service-amount">Service / fees</label>
                            <input
                                id="service-amount"
                                className="amount"
                                type="text"
                                inputMode="decimal"
                                value={service}
                                onChange={(e) => setService(sanitizeDecimal(e.target.value))}
                                placeholder="0"
                            />
                        </div>

                        <div className="summary-row">
                            <label htmlFor="discount-amount">Discount</label>
                            <input
                                id="discount-amount"
                                className="amount"
                                type="text"
                                inputMode="decimal"
                                value={discount}
                                onChange={(e) => setDiscount(sanitizeDecimal(e.target.value))}
                                placeholder="0"
                            />
                        </div>

                        {(receipt.rounding || toNumber(rounding) !== 0) && (
                            <div className="summary-row">
                                <label htmlFor="rounding-amount">Rounding</label>
                                <input
                                    id="rounding-amount"
                                    className="amount"
                                    type="text"
                                    inputMode="decimal"
                                    value={rounding}
                                    onChange={(e) =>
                                        setRounding(sanitizeDecimal(e.target.value, { allowNegative: true }))
                                    }
                                    placeholder="0"
                                />
                            </div>
                        )}

                        <div className="summary-total">
                            <span>Total</span>
                            <strong>{money(totals.total)}</strong>
                        </div>
                    </div>

                    <div className="confirm-row">
                        <button
                            type="button"
                            className="button primary"
                            disabled={!canConfirm}
                            onClick={() => {
                                setSplitStarted(true);
                                goTo("split");
                            }}
                        >
                            Continue to split →
                        </button>

                        {!canConfirm && items.length > 0 && (
                            <p className="hint">Every item needs a name and a quantity above zero.</p>
                        )}
                    </div>

                    <details className="raw">
                        <summary>Show raw text from the image</summary>
                        <pre>{(ocr?.lines || []).map((line) => line.text).join("\n")}</pre>
                    </details>
                </div>
            </div>
            </div>
        </section>
    );
}

export default ReceiptReview;
