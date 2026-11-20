const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

async function request(path, options, fallbackMessage) {
    let response;

    try {
        response = await fetch(`${API_URL}${path}`, options);
    } catch {
        throw new Error(
            "Can't reach the SmartSplit server. Make sure the backend is running."
        );
    }

    let data = null;

    try {
        data = await response.json();
    } catch {
        // Non-JSON body (proxy error page, crash). Fall through to the generic message.
    }

    if (!response.ok) {
        const detail = data?.detail;
        throw new Error(
            typeof detail === "string" ? detail : fallbackMessage
        );
    }

    return data;
}

export function uploadReceipt(file) {
    const formData = new FormData();
    formData.append("file", file);

    return request(
        "/api/receipts/upload",
        { method: "POST", body: formData },
        "Upload failed. Please try again."
    );
}

export function analyzeReceipt(receiptId) {
    return request(
        `/api/receipts/${receiptId}/analyze`,
        { method: "POST" },
        "Receipt analysis failed. Please try again."
    );
}
