
const API_URL = "http://127.0.0.1:8000";

export async function uploadReceipt(file) {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(
        `${API_URL}/api/receipts/upload`,
        {
            method: "POST",
            body: formData
        }
    );

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || "Upload failed");
    }

    return data;
}

export async function analyzeReceipt(receiptId){
    const response = await fetch(
        `${API_URL}/api/receipts/${receiptId}/analyze`,
        {
            method: "POST"
        }
    );

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || "Receipt analysis failed");
    }
    return data;
}
