
import "./App.css";
import ReceiptUploader from "./components/ReceiptUploader";

function App() {
    return (
        <main className="app-shell">
            <header className="topbar">
                <a className="brand" href="/" aria-label="SmartSplit home">
                    <span className="brand-symbol">S</span>
                    <span>smartsplit</span>
                </a>

                <span className="topbar-label">
                    RECEIPT WORKSPACE
                </span>
            </header>

            <section className="intro">
                <p className="intro-kicker">
                    RECEIPT ANALYSIS · MADE SIMPLE
                </p>

                <h1>
                    From receipt to
                    <br />
                    <span>everyone's share.</span>
                </h1>

                <p className="intro-description">
                    Turn a receipt photo into organized expenses.
                    Review every item, then split the bill your way.
                </p>
            </section>

            <ReceiptUploader />

            <footer className="app-footer">
                <span>SMARTSPLIT</span>
                <span>Less calculating. More sharing.</span>
            </footer>
        </main>
    );
}

export default App;
