
import { useState } from "react";

function formatIDR(value) {
    return new Intl.NumberFormat("id-ID", {
        style: "currency",
        currency: "IDR",
        maximumFractionDigits: 0
    }).format(value || 0);
}

function ReceiptReview({ receipt }) {
    const [merchant, setMerchant] = useState(
        receipt.merchant_name || ""
    );

    const [items, setItems] = useState(
        (receipt.items || []).map((item) => ({
            ...item,
            quantity: Number(item.quantity || 1),
            unit_price: Number(item.unit_price || 0)
        }))
    );

    const [tax, setTax] = useState(Number(receipt.tax || 0));
    const [serviceCharge, setServiceCharge] = useState(
        Number(receipt.service_charge || 0)
    );
    const [discount, setDiscount] = useState(
        Number(receipt.discount || 0)
    );
    const [confirmed, setConfirmed] = useState(false);

    // Calculate the total for each item.
    const subtotal = items.reduce(
        (sum, item) =>
            sum + item.quantity * item.unit_price,
        0
    );

    const total = subtotal + tax + serviceCharge - discount;

    function updateItem(index, field, value) {
        setConfirmed(false);

        setItems((currentItems) =>
            currentItems.map((item, itemIndex) =>
                itemIndex === index
                    ? { ...item, [field]: value }
                    : item
            )
        );
    }

    function addItem() {
        setConfirmed(false);

        setItems((currentItems) => [
            ...currentItems,
            {
                name: "",
                quantity: 1,
                unit: "pcs",
                unit_price: 0
            }
        ]);
    }

    function removeItem(index) {
        setConfirmed(false);

        setItems((currentItems) =>
            currentItems.filter(
                (_, itemIndex) => itemIndex !== index
            )
        );
    }

    return (
        <section className="review-section">
            <div className="section-heading">
                <div>
                    <span className="eyebrow">STEP 02</span>
                    <h2>Review your receipt</h2>
                    <p>
                        Check the extracted information and
                        correct anything that needs attention.
                    </p>
                </div>

                <span className="review-status">
                    Needs review
                </span>
            </div>

            <div className="receipt-card">
                <div className="receipt-header">
                    <label htmlFor="merchant">
                        Merchant name
                    </label>

                    <input
                        id="merchant"
                        type="text"
                        value={merchant}
                        onChange={(e) => {
                            setMerchant(e.target.value);
                            setConfirmed(false);
                        }}
                    />
                </div>

                <div className="items-header">
                    <h3>Items</h3>
                    <span>{items.length} items</span>
                </div>

                <div className="item-list">
                    {items.map((item, index) => (
                        <div className="receipt-item" key={index}>
                            <div className="item-main">
                                <div className="item-name-field">
                                    <label>Item name</label>
                                    <input
                                        type="text"
                                        value={item.name}
                                        onChange={(e) =>
                                            updateItem(
                                                index,
                                                "name",
                                                e.target.value
                                            )
                                        }
                                        placeholder="Item name"
                                    />
                                </div>

                                <button
                                    className="remove-item"
                                    type="button"
                                    onClick={() => removeItem(index)}
                                    aria-label={`Remove ${item.name}`}
                                >
                                    Remove
                                </button>
                            </div>

                            <div className="item-fields">
                                <div>
                                    <label>Quantity</label>
                                    <input
                                        type="number"
                                        min="0"
                                        step="1"
                                        value={item.quantity}
                                        onChange={(e) =>
                                            updateItem(
                                                index,
                                                "quantity",
                                                Math.max(
                                                    0,
                                                    Number(e.target.value)
                                                )
                                            )
                                        }
                                    />
                                </div>

                                <div>
                                    <label>Unit</label>
                                    <input
                                        type="text"
                                        value={item.unit || "pcs"}
                                        onChange={(e) =>
                                            updateItem(
                                                index,
                                                "unit",
                                                e.target.value
                                            )
                                        }
                                    />
                                </div>

                                <div>
                                    <label>Unit price (Rp)</label>
                                    <input
                                        type="number"
                                        min="0"
                                        value={item.unit_price}
                                        onChange={(e) =>
                                            updateItem(
                                                index,
                                                "unit_price",
                                                Math.max(
                                                    0,
                                                    Number(e.target.value)
                                                )
                                            )
                                        }
                                    />
                                </div>

                                <div className="item-total">
                                    <label>Line total</label>
                                    <strong>
                                        {formatIDR(
                                            item.quantity *
                                            item.unit_price
                                        )}
                                    </strong>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>

                <button
                    type="button"
                    className="add-item-button"
                    onClick={addItem}
                >
                    + Add another item
                </button>

                <div className="receipt-summary">
                    <h3>Payment summary</h3>

                    <div className="summary-row">
                        <span>Subtotal</span>
                        <strong>{formatIDR(subtotal)}</strong>
                    </div>

                    <div className="summary-row">
                        <label htmlFor="tax">Tax (Rp)</label>
                        <input
                            id="tax"
                            type="number"
                            min="0"
                            value={tax}
                            onChange={(e) => {
                                setTax(Math.max(0, Number(e.target.value)));
                                setConfirmed(false);
                            }}
                        />
                    </div>

                    <div className="summary-row">
                        <label htmlFor="service">Service charge (Rp)</label>
                        <input
                            id="service"
                            type="number"
                            min="0"
                            value={serviceCharge}
                            onChange={(e) => {
                                setServiceCharge(
                                    Math.max(0, Number(e.target.value))
                                );
                                setConfirmed(false);
                            }}
                        />
                    </div>

                    <div className="summary-row">
                        <label htmlFor="discount">Discount (Rp)</label>
                        <input
                            id="discount"
                            type="number"
                            min="0"
                            value={discount}
                            onChange={(e) => {
                                setDiscount(
                                    Math.max(0, Number(e.target.value))
                                );
                                setConfirmed(false);
                            }}
                        />
                    </div>

                    <div className="summary-total">
                        <span>Grand total</span>
                        <strong>{formatIDR(total)}</strong>
                    </div>
                </div>

                <button
                    type="button"
                    className="confirm-button"
                    disabled={
                        items.length === 0 ||
                        items.some(
                            (item) =>
                                !item.name.trim() ||
                                item.quantity <= 0
                        ) ||
                        total < 0
                    }
                    onClick={() => setConfirmed(true)}
                >
                    Confirm receipt
                </button>

                {confirmed && (
                    <p className="confirmation-message">
                        Receipt confirmed. Ready for bill splitting.
                    </p>
                )}
            </div>
        </section>
    );
}

export default ReceiptReview;
