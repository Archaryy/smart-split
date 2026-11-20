import "./App.css";
import ReceiptUploader from "./components/ReceiptUploader";

function App() {
    return (
        <div className="app-shell">
            <header className="topbar">
                <a className="brand" href="/" aria-label="SmartSplit home">
                    <span className="brand-symbol" aria-hidden="true">S</span>
                    <span>SmartSplit</span>
                </a>
            </header>

            <main>
                <ReceiptUploader />
            </main>
        </div>
    );
}

export default App;
