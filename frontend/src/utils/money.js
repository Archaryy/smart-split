const NO_DECIMAL_CURRENCIES = new Set(["IDR", "JPY", "KRW", "VND"]);

export const CURRENCIES = ["IDR", "USD", "EUR", "GBP", "SGD", "MYR", "JPY"];

export function decimalsFor(currency) {
    return NO_DECIMAL_CURRENCIES.has(currency) ? 0 : 2;
}

export function formatMoney(value, currency = "IDR") {
    const decimals = decimalsFor(currency);
    const amount = Number.isFinite(value) ? value : 0;

    try {
        return new Intl.NumberFormat(currency === "IDR" ? "id-ID" : "en-US", {
            style: "currency",
            currency,
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        }).format(amount);
    } catch {
        return amount.toFixed(decimals);
    }
}

// Money inputs are edited as strings so partial input like "12." is allowed.
export function toNumber(text) {
    const value = Number.parseFloat(text);
    return Number.isFinite(value) ? value : 0;
}

export function sanitizeDecimal(text, { allowNegative = false } = {}) {
    let cleaned = text.replace(allowNegative ? /[^0-9.-]/g : /[^0-9.]/g, "");
    const firstDot = cleaned.indexOf(".");

    if (firstDot !== -1) {
        cleaned =
            cleaned.slice(0, firstDot + 1) +
            cleaned.slice(firstDot + 1).replace(/\./g, "");
    }

    return cleaned;
}

export function roundMoney(value) {
    return Math.round(value * 100) / 100;
}
