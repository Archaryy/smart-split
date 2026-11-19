
import { useState } from "react";
import { uploadReceipt, analyzeReceipt } from "../services/api";
import ReceiptReview from "./ReceiptReview";

function formatFileSize(bytes) {
    if (bytes < 1024 * 1024) {
        return `${(bytes / 1024).toFixed(0)} KB`;
    }

    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function ReceiptUploader() {
    const [file, setFile] = useState(null);
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [status, setStatus] = useState("");
    const [error, setError] = useState("");

    function handleFileChange(event) {
        const selectedFile = event.target.files?.[0] || null;

        setError("");
        setStatus("");
        setResult(null);

        if (!selectedFile) {
            setFile(null);
            return;
        }

        const allowedTypes = [
            "image/jpeg",
            "image/png",
            "image/webp"
        ];

        if (!allowedTypes.includes(selectedFile.type)) {
            setFile(null);
            setError("Please select a JPG, PNG, or WEBP image.");
            return;
        }

        if (selectedFile.size > 10 * 1024 * 1024) {
            setFile(null);
            setError("File size must be 10 MB or less.");
            return;
        }

        setFile(selectedFile);
    }

    async function handleUpload() {
        if (!file || loading) return;

        setLoading(true);
        setError("");
        setResult(null);

        try {
            setStatus("Uploading your receipt...");

            const uploadData = await uploadReceipt(file);

            setStatus("Extracting receipt information...");

            const analysisData = await analyzeReceipt(
                uploadData.receipt_id
            );

            if (!analysisData.receipt) {
                throw new Error("No receipt data was returned.");
            }

            setResult(analysisData);
            setStatus("");
        } catch (err) {
            setError(err.message || "Something went wrong.");
            setStatus("");
        } finally {
            setLoading(false);
        }
    }

    function resetUploader() {
        setFile(null);
        setResult(null);
        setStatus("");
        setError("");
    }

    if (result) {
        return (
            <div className="upload-results">
                <div className="analysis-complete">
                    <span>✓</span>
                    Receipt successfully analyzed
                </div>

                <ReceiptReview
                    key={result.receipt_id}
                    receipt={result.receipt}
                />

                <details className="ocr-details">
                    <summary>View original OCR output</summary>
                    <pre>{JSON.stringify(result.ocr, null, 2)}</pre>
                </details>

                <button
                    className="secondary-button"
                    onClick={resetUploader}
                >
                    Analyze another receipt
                </button>
            </div>
        );
    }

    return (
        <section className="upload-card">
            <div className="upload-card-heading">
                <span className="upload-step-label">01 / UPLOAD</span>
                <h2>Upload your receipt</h2>
                <p>
                    Start with a clear photo of your receipt.
                    We'll handle the extraction.
                </p>
            </div>

            <label
                htmlFor="receipt-file"
                className={`upload-dropzone ${file ? "has-file" : ""}`}
            >
                <span className="upload-symbol">
                    {file ? "✓" : "↑"}
                </span>

                {file ? (
                    <>
                        <strong>{file.name}</strong>
                        <span className="upload-file-size">
                            {formatFileSize(file.size)}
                        </span>
                        <span className="upload-change">
                            Choose a different file
                        </span>
                    </>
                ) : (
                    <>
                        <strong>Choose a receipt image</strong>
                        <span>Browse files from your device</span>
                    </>
                )}
            </label>

            <input
                id="receipt-file"
                className="upload-file-input"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={handleFileChange}
                disabled={loading}
            />

            <div className="upload-file-guidance">
                <span>JPG, PNG or WEBP</span>
                <span>Maximum 10 MB</span>
            </div>

            {error && (
                <p className="upload-error" role="alert">
                    {error}
                </p>
            )}

            {status && (
                <p className="upload-progress" role="status">
                    <span className="loading-dot" />
                    {status}
                </p>
            )}

            <button
                className="upload-submit"
                onClick={handleUpload}
                disabled={!file || loading}
            >
                {loading ? "Processing receipt..." : "Analyze receipt"}
                {!loading && <span>→</span>}
            </button>

            <p className="upload-privacy">
                Your receipt is processed by SmartSplit's local OCR service.
            </p>
        </section>
    );
}

export default ReceiptUploader;
