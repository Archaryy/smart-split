
import { useState } from "react";
import { uploadReceipt } from "../services/api";

function ReceiptUploader() {
    const [file, setFile] = useState(null);
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    async function handleUpload() {
        if (!file) return;

        setLoading(true);
        setError("");
        setResult(null);

        try {
            const data = await uploadReceipt(file);
            setResult(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }

    return (
        <div>
            <h2>Upload your receipt</h2>

            <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={(e) => {
                    setFile(e.target.files[0]);
                    setResult(null);
                    setError("");
                }}
            />

            {file && <p>Selected: {file.name}</p>}

            <button
                onClick={handleUpload}
                disabled={!file || loading}
            >
                {loading ? "Uploading..." : "Upload receipt"}
            </button>

            {error && (
                <p style={{ color: "red" }}>{error}</p>
            )}

            {result && (
                <pre>
                    {JSON.stringify(result, null, 2)}
                </pre>
            )}
        </div>
    );
}

export default ReceiptUploader;
