import { useEffect, useRef, useState } from "react";
import { uploadReceipt, analyzeReceipt } from "../services/api";
import { prepareImage } from "../utils/image";
import ReceiptReview from "./ReceiptReview";
import Stepper from "./Stepper";

// Large phone photos are shrunk before upload, so the limit here is generous.
const MAX_FILE_SIZE = 25 * 1024 * 1024;
const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];

const TIPS = [
    "Lay the receipt flat",
    "Use even lighting, no glare",
    "Keep the whole receipt in frame"
];

function ReceiptUploader() {
    const fileInputRef = useRef(null);
    const cameraInputRef = useRef(null);
    // Only phones/tablets get a "Take photo" button; on desktop it would just open the file picker.
    const hasCamera = window.matchMedia("(pointer: coarse)").matches;

    const previewRef = useRef("");

    const [file, setFile] = useState(null);
    const [previewUrl, setPreviewUrl] = useState("");
    const [isDragging, setIsDragging] = useState(false);
    const [phase, setPhase] = useState("idle"); // idle | uploading | reading
    const [elapsed, setElapsed] = useState(0);
    const [error, setError] = useState("");
    const [result, setResult] = useState(null);

    const loading = phase !== "idle";

    // The preview URL is created when a file is chosen and released when it
    // is replaced, cleared, or the component goes away.
    function replaceFile(nextFile) {
        if (previewRef.current) URL.revokeObjectURL(previewRef.current);

        previewRef.current = nextFile ? URL.createObjectURL(nextFile) : "";
        setPreviewUrl(previewRef.current);
        setFile(nextFile);
    }

    useEffect(() => () => {
        if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    }, []);

    // Reading a receipt can take a while; show that something is happening.
    useEffect(() => {
        if (phase !== "reading") return;

        const timer = setInterval(() => setElapsed((s) => s + 1), 1000);
        return () => clearInterval(timer);
    }, [phase]);

    function selectFile(selectedFile) {
        setError("");
        setResult(null);

        if (!selectedFile) return;

        if (!ALLOWED_TYPES.includes(selectedFile.type)) {
            replaceFile(null);
            setError("Choose a JPG, PNG or WEBP image.");
            return;
        }

        if (selectedFile.size > MAX_FILE_SIZE) {
            replaceFile(null);
            setError("That image is larger than 25 MB. Choose a smaller file.");
            return;
        }

        replaceFile(selectedFile);
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

        setError("");
        setElapsed(0);
        setPhase("uploading");

        try {
            const uploadData = await uploadReceipt(await prepareImage(file));

            setPhase("reading");

            const analysisData = await analyzeReceipt(uploadData.receipt_id);

            if (!analysisData.receipt) {
                throw new Error("The server returned no receipt data.");
            }

            setResult(analysisData);
        } catch (err) {
            setError(err.message || "Something went wrong. Please try again.");
        } finally {
            setPhase("idle");
        }
    }

    function resetUpload() {
        replaceFile(null);
        setResult(null);
        setError("");
        setPhase("idle");
    }

    if (result) {
        return (
            <ReceiptReview
                key={result.receipt_id}
                receipt={result.receipt}
                ocr={result.ocr}
                imageUrl={previewUrl}
                onReset={resetUpload}
            />
        );
    }

    return (
        <section className="upload-view">
            <Stepper current={0} narrow />
            <h1>Upload a receipt</h1>
            <p className="lead">
                We'll read the items and prices so you can check them before
                splitting.
            </p>

            <div
                className={`dropzone ${isDragging ? "is-dragging" : ""} ${
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
                    <div className="selected-file">
                        <img
                            src={previewUrl}
                            alt="Selected receipt"
                            className="selected-thumb"
                        />

                        <div className="selected-meta">
                            <strong title={file.name}>{file.name}</strong>
                            <span>{(file.size / (1024 * 1024)).toFixed(2)} MB</span>
                            <button
                                className="link-button"
                                type="button"
                                onClick={resetUpload}
                                disabled={loading}
                            >
                                Choose a different image
                            </button>
                        </div>
                    </div>
                ) : (
                    <div className="dropzone-empty">
                        <svg
                            className="dropzone-icon"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.6"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            aria-hidden="true"
                        >
                            <path d="M12 16V4" />
                            <path d="m7 9 5-5 5 5" />
                            <path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
                        </svg>

                        <p className="dropzone-title">Drop a receipt photo here</p>

                        <div className="dropzone-buttons">
                            {hasCamera && (
                                <button
                                    className="button primary"
                                    type="button"
                                    onClick={() => cameraInputRef.current?.click()}
                                >
                                    Take photo
                                </button>
                            )}
                            <button
                                className="button secondary"
                                type="button"
                                onClick={() => fileInputRef.current?.click()}
                            >
                                Choose image
                            </button>
                        </div>

                        <span className="hint">JPG, PNG or WEBP · up to 25 MB</span>

                        <input
                            ref={fileInputRef}
                            className="visually-hidden"
                            type="file"
                            accept="image/jpeg,image/png,image/webp"
                            onChange={handleFileChange}
                            tabIndex={-1}
                        />
                        <input
                            ref={cameraInputRef}
                            className="visually-hidden"
                            type="file"
                            accept="image/*"
                            capture="environment"
                            onChange={handleFileChange}
                            tabIndex={-1}
                        />
                    </div>
                )}
            </div>

            {error && (
                <p className="notice error" role="alert">
                    {error}
                </p>
            )}

            {loading && (
                <div className="progress" role="status">
                    <div className="progress-bar" aria-hidden="true" />
                    <p>
                        {phase === "uploading"
                            ? "Uploading…"
                            : `Reading the receipt… ${elapsed}s`}
                    </p>
                    {phase === "reading" && elapsed >= 8 && (
                        <p className="hint">
                            Hard-to-read receipts can take a minute or two.
                        </p>
                    )}
                </div>
            )}

            <div className="actions">
                <button
                    className="button primary"
                    type="button"
                    onClick={handleAnalyze}
                    disabled={!file || loading}
                >
                    {loading ? "Working…" : "Read receipt"}
                </button>
            </div>

            <ul className="tips" aria-label="Tips for a good photo">
                {TIPS.map((tip) => (
                    <li key={tip}>{tip}</li>
                ))}
            </ul>
        </section>
    );
}

export default ReceiptUploader;
