
import { useEffect, useRef, useState } from "react";
import { uploadReceipt, analyzeReceipt } from "../services/api";
import ReceiptReview from "./ReceiptReview";

const MAX_FILE_SIZE = 10 * 1024 * 1024;
const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];

function ReceiptUploader() {
    const fileInputRef = useRef(null);

    const [file, setFile] = useState(null);
    const [previewUrl, setPreviewUrl] = useState("");
    const [isDragging, setIsDragging] = useState(false);
    const [loading, setLoading] = useState(false);
    const [status, setStatus] = useState("");
    const [error, setError] = useState("");
    const [result, setResult] = useState(null);

    useEffect(() => {
        if (!file) {
            setPreviewUrl("");
            return;
        }

        const url = URL.createObjectURL(file);
        setPreviewUrl(url);

        return () => URL.revokeObjectURL(url);
    }, [file]);

    function selectFile(selectedFile) {
        setError("");
        setStatus("");
        setResult(null);

        if (!selectedFile) return;

        if (!ALLOWED_TYPES.includes(selectedFile.type)) {
            setFile(null);
            setError("Choose a JPG, PNG, or WEBP image.");
            return;
        }

        if (selectedFile.size > MAX_FILE_SIZE) {
            setFile(null);
            setError("This image is larger than 10 MB. Choose a smaller file.");
            return;
        }

        setFile(selectedFile);
    }

    function handleFileChange(event) {
        selectFile(event.target.files?.[0]);
        event.target.value = "";
    }

    function handleDrop(event) {
        event.preventDefault();
        setIsDragging(false);

        if (loading) return;

        selectFile(event.dataTransfer.files?.[0]);
    }

    async function handleAnalyze() {
        if (!file || loading) return;

        setLoading(true);
        setError("");
        setStatus("Uploading your receipt...");

        try {
            const uploadData = await uploadReceipt(file);

            setStatus("Reading receipt text...");

            const analysisData = await analyzeReceipt(
                uploadData.receipt_id
            );

            if (!analysisData.receipt) {
                throw new Error("The server returned no receipt data.");
            }

            setResult(analysisData);
            setStatus("");
        } catch (err) {
            setError(err.message || "Something went wrong. Please try again.");
            setStatus("");
        } finally {
            setLoading(false);
        }
    }

    function resetUpload() {
        setFile(null);
        setResult(null);
        setError("");
        setStatus("");
        setLoading(false);
    }

    if (result) {
        return (
            <section className="workspace">
                <div className="success-line">
                    <span className="success-mark">✓</span>
                    <span>Receipt successfully analyzed</span>
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
                    className="text-button"
                    type="button"
                    onClick={resetUpload}
                >
                    ← Analyze another receipt
                </button>
            </section>
        );
    }

    return (
        <section className="workspace">
            <div className="section-meta">
                <span className="step-number">01</span>
                <div>
                    <h2>Upload a receipt</h2>
                    <p>Start with a clear photo or scan of your receipt.</p>
                </div>
            </div>

            <div
                className={`upload-panel ${isDragging ? "is-dragging" : ""} ${
                    file ? "has-file" : ""
                }`}
                onDragOver={(event) => {
                    event.preventDefault();
                    if (!loading) setIsDragging(true);
                }}
                onDragLeave={(event) => {
                    if (!event.currentTarget.contains(event.relatedTarget)) {
                        setIsDragging(false);
                    }
                }}
                onDrop={handleDrop}
            >
                {file ? (
                    <div className="file-preview">
                        <div className="preview-image-wrap">
                            <img
                                src={previewUrl}
                                alt="Selected receipt preview"
                                className="preview-image"
                            />
                        </div>

                        <div className="file-information">
                            <span className="file-label">SELECTED FILE</span>
                            <strong title={file.name}>{file.name}</strong>
                            <span>
                                {(file.size / (1024 * 1024)).toFixed(2)} MB
                            </span>
                            <button
                                className="text-button"
                                type="button"
                                onClick={resetUpload}
                                disabled={loading}
                            >
                                Remove image
                            </button>
                        </div>
                    </div>
                ) : (
                    <div className="dropzone-content">
                        <div className="upload-symbol" aria-hidden="true">
                            <svg
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="1.6"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                            >
                                <path d="M12 16V4" />
                                <path d="m7 9 5-5 5 5" />
                                <path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
                            </svg>
                        </div>

                        <h3>Drop your receipt here</h3>
                        <p>or choose an image from your device</p>

                        <button
                            className="choose-file-button"
                            type="button"
                            onClick={() => fileInputRef.current?.click()}
                            disabled={loading}
                        >
                            Choose image
                        </button>

                        <input
                            ref={fileInputRef}
                            className="file-input"
                            type="file"
                            accept="image/jpeg,image/png,image/webp"
                            onChange={handleFileChange}
                            disabled={loading}
                        />

                        <span className="file-requirements">
                            JPG, PNG or WEBP · Maximum 10 MB
                        </span>
                    </div>
                )}
            </div>

            {error && (
                <p className="upload-error" role="alert">
                    <span>!</span>
                    {error}
                </p>
            )}

            {status && (
                <p className="upload-status" role="status">
                    <span className="loading-dot" />
                    {status}
                </p>
            )}

            <div className="upload-actions">
                <div className="privacy-note">
                    <span aria-hidden="true">↳</span>
                    Your receipt is processed by your SmartSplit backend.
                </div>

                <button
                    className="analyze-button"
                    type="button"
                    onClick={handleAnalyze}
                    disabled={!file || loading}
                >
                    {loading ? "Processing..." : "Analyze receipt"}
                    {!loading && <span aria-hidden="true">→</span>}
                </button>
            </div>
        </section>
    );
}

export default ReceiptUploader;
