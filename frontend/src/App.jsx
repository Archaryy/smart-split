
import "./App.css";
import ReceiptUploader from "./components/ReceiptUploader";

function App() {
    return (
        <main className="workspace-shell">
            <header className="workspace-header">
                <a href="/" className="workspace-brand">
                    <span className="workspace-brand-mark">S</span>
                    <span>smartsplit</span>
                </a>

                <span className="workspace-header-label">
                    RECEIPT WORKSPACE
                </span>
            </header>

            <section className="upload-layout">
                <div className="upload-intro">
                    <span className="upload-eyebrow">
                        RECEIPT ANALYZER & BILL SPLITTER
                    </span>

                    <h1>
                        From receipt to
                        <br />
                        <span>everyone's share.</span>
                    </h1>

                    <p className="upload-description">
                        Turn a receipt photo into organized expenses.
                        Review the extracted items, then split the bill
                        with confidence.
                    </p>

                    <div className="workflow-list">
                        <div className="workflow-step">
                            <span className="workflow-number">01</span>
                            <div>
                                <strong>Upload receipt</strong>
                                <p>Choose a photo of your receipt.</p>
                            </div>
                        </div>

                        <div className="workflow-step">
                            <span className="workflow-number">02</span>
                            <div>
                                <strong>Review items</strong>
                                <p>Check the extracted names and prices.</p>
                            </div>
                        </div>

                        <div className="workflow-step">
                            <span className="workflow-number">03</span>
                            <div>
                                <strong>Split the bill</strong>
                                <p>Assign items and calculate each share.</p>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="upload-panel">
                    <ReceiptUploader />
                </div>
            </section>

            <footer className="workspace-footer">
                <span>SMARTSPLIT</span>
                <span>Make every share count.</span>
            </footer>
        </main>
    );
}

export default App;
