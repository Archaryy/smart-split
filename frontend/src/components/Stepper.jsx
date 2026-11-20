const STEPS = ["Upload", "Check", "Split"];

// Shows where the user is in the flow: upload a photo, check the items, split the bill.
function Stepper({ current, narrow = false }) {
    return (
        <ol className={`stepper ${narrow ? "narrow" : ""}`} aria-label="Progress">
            {STEPS.map((label, index) => {
                const state = index < current ? "done" : index === current ? "current" : "todo";

                return (
                    <li
                        key={label}
                        className={`step ${state}`}
                        aria-current={state === "current" ? "step" : undefined}
                    >
                        <span className="step-dot" aria-hidden="true">
                            {state === "done" ? "✓" : index + 1}
                        </span>
                        <span className="step-label">{label}</span>
                    </li>
                );
            })}
        </ol>
    );
}

export default Stepper;
