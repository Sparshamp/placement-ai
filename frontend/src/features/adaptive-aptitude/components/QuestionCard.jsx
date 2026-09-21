import { useState, useEffect } from "react";

const DIFFICULTY_COLOR = { Easy: "#4ade80", Medium: "#e8a33d", Hard: "#f26d6d" };
// match_following questions are pre-flattened into MCQ form upstream (each
// option_a-d is a full a-i/b-ii/... mapping, correct_answer is a single
// letter) -- so they're scored and rendered exactly like mcq/image_based.
const SINGLE_ANSWER_TYPES = new Set(["mcq", "image_based", "match_following"]);
const MULTI_SELECT_TYPES = new Set(["multi_select"]);
const FREE_TEXT_ANSWER_TYPES = new Set(["numerical", "fill_blank"]);

/**
 * @param question   current question object from the API (correct_answer
 *                    intentionally absent until answered -- see backend)
 * @param onSubmit    (selectedAnswer: string) => void -- for multi_select,
 *                     every chosen letter joined with ";" e.g. "A;C"
 * @param onSkip      () => void -- used for unsupported types
 */
export default function QuestionCard({ question, onSubmit, onSkip }) {
  const [choice, setChoice] = useState(null);       // single-answer types
  const [multiChoice, setMultiChoice] = useState([]); // multi_select: array of letters
  const [freeText, setFreeText] = useState("");
  const [emptyWarning, setEmptyWarning] = useState(false);

  // Reset local answer state whenever a new question is shown
  useEffect(() => {
    setChoice(null);
    setMultiChoice([]);
    setFreeText("");
    setEmptyWarning(false);
  }, [question?.question_id]);

  if (!question) return null;

  const qtype = question.canonical_question_type || "mcq";
  const diff = question.difficulty || "Medium";
  const isMultiSelect = MULTI_SELECT_TYPES.has(qtype);

  const options = {
    A: question.option_a, B: question.option_b,
    C: question.option_c, D: question.option_d,
  };

  function toggleMultiChoice(letter) {
    setMultiChoice((prev) =>
      prev.includes(letter) ? prev.filter((l) => l !== letter) : [...prev, letter]
    );
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (isMultiSelect) {
      if (multiChoice.length) onSubmit([...multiChoice].sort().join(";"));
      return;
    }
    if (SINGLE_ANSWER_TYPES.has(qtype)) {
      if (choice) onSubmit(choice);
      return;
    }
    if (FREE_TEXT_ANSWER_TYPES.has(qtype)) {
      const trimmed = freeText.trim();
      if (!trimmed) {
        setEmptyWarning(true);
        return;
      }
      onSubmit(trimmed);
    }
  }

  return (
    <div className="card question-card">
      <div className="question-meta">
        <span className="difficulty-dot" style={{ background: DIFFICULTY_COLOR[diff] || "#9297ac" }} />
        <span className="muted">{diff}</span>
        <span className="faint">·</span>
        <span className="muted mono">
          {question.canonical_subject} › {question.canonical_topic} › {question.subtopic}
        </span>
      </div>

      <h2 className="question-text">{question.question}</h2>

      {question.image_url && (
        <img src={question.image_url} alt="" className="question-image" />
      )}

      {isMultiSelect && (
        <p className="faint" style={{ marginTop: "-0.4rem", marginBottom: "0.8rem" }}>
          Select all that apply.
        </p>
      )}

      {(SINGLE_ANSWER_TYPES.has(qtype) || isMultiSelect) && (
        <form onSubmit={handleSubmit}>
          <div
            className="option-list"
            role={isMultiSelect ? "group" : "radiogroup"}
            aria-label={isMultiSelect ? "Select all correct answers" : "Select an answer"}
          >
            {Object.entries(options)
              .filter(([, text]) => text)
              .map(([letter, text]) => {
                const selected = isMultiSelect ? multiChoice.includes(letter) : choice === letter;
                return (
                  <label key={letter} className={`option-row ${selected ? "option-row--selected" : ""}`}>
                    <input
                      type={isMultiSelect ? "checkbox" : "radio"}
                      name="answer"
                      value={letter}
                      checked={selected}
                      onChange={() => (isMultiSelect ? toggleMultiChoice(letter) : setChoice(letter))}
                    />
                    <span className="option-letter">{letter}</span>
                    <span>{text}</span>
                  </label>
                );
              })}
          </div>
          <button
            type="submit"
            className="primary"
            disabled={isMultiSelect ? multiChoice.length === 0 : !choice}
          >
            Submit Answer
          </button>
        </form>
      )}

      {FREE_TEXT_ANSWER_TYPES.has(qtype) && (
        <form onSubmit={handleSubmit}>
          <label className="muted" htmlFor="free-text-answer">Your answer</label>
          <input
            id="free-text-answer"
            type="text"
            value={freeText}
            onChange={(e) => { setFreeText(e.target.value); setEmptyWarning(false); }}
            autoComplete="off"
          />
          {emptyWarning && <p className="warning-text">Enter an answer before submitting.</p>}
          <div style={{ marginTop: "0.8rem" }}>
            <button type="submit" className="primary">Submit Answer</button>
          </div>
        </form>
      )}

      {!SINGLE_ANSWER_TYPES.has(qtype) && !isMultiSelect && !FREE_TEXT_ANSWER_TYPES.has(qtype) && (
        <div>
          <p className="warning-text">
            Question type <code>{qtype}</code> isn't scored by the backend yet. Skipping.
          </p>
          <button onClick={onSkip}>Skip to next question</button>
        </div>
      )}
    </div>
  );
}