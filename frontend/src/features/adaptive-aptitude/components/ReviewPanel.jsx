import { useState } from "react";

/**
 * Read-only, paged view of everything answered this session. Deliberately
 * NOT editable -- each answer causally updates BKT/EMA mastery and the
 * next question is chosen based on that update; letting someone change a
 * past answer would leave the mastery state and question sequence
 * silently inconsistent with each other, and the backend has no "undo".
 */
function splitMulti(raw) {
  return new Set(String(raw || "").split(";").map((s) => s.trim().toUpperCase()).filter(Boolean));
}

export default function ReviewPanel({ log, onClose }) {
  const [index, setIndex] = useState(0);
  const entry = log[index];
  if (!entry) return null;

  const isMultiSelect = entry.questionType === "multi_select";
  const correctSet = isMultiSelect ? splitMulti(entry.correctAnswer) : null;
  const selectedSet = isMultiSelect ? splitMulti(entry.selectedAnswer) : null;
  const status = entry.answerDetail?.status || (entry.correct ? "correct" : "incorrect");
  const statusLabel = { correct: "✅ Correct", partial: "🟡 Partially correct", incorrect: "❌ Incorrect" }[status];

  return (
    <div className="card review-panel">
      <div className="review-header">
        <h3>📖 Reviewing question {index + 1} of {log.length}</h3>
        <button className="subtle" onClick={onClose}>↩ Back to current question</button>
      </div>

      <div className="review-nav">
        <button disabled={index === 0} onClick={() => setIndex((i) => i - 1)}>◀ Previous</button>
        <button disabled={index === log.length - 1} onClick={() => setIndex((i) => i + 1)}>Next ▶</button>
      </div>

      <hr className="review-divider" />

      <div className="question-meta">
        <span className="muted">{entry.difficulty}</span>
        <span className="faint">·</span>
        <span className="muted mono">{entry.canonicalSubject} › {entry.canonicalTopic}</span>
      </div>
      <h2 className="question-text">{entry.questionText}</h2>
      {isMultiSelect && <p className="faint" style={{ marginTop: "-0.6rem" }}>Select all that apply.</p>}

      {entry.options && Object.values(entry.options).some(Boolean) ? (
        <div className="option-list">
          {Object.entries(entry.options)
            .filter(([, text]) => text)
            .map(([letter, text]) => {
              const isCorrect = isMultiSelect ? correctSet.has(letter) : letter === entry.correctAnswer;
              const isPicked = isMultiSelect ? selectedSet.has(letter) : letter === entry.selectedAnswer;
              let cls = "option-row option-row--review";
              if (isCorrect) cls += " option-row--correct";
              else if (isPicked) cls += " option-row--incorrect";
              return (
                <div key={letter} className={cls}>
                  <span className="option-letter">{letter}</span>
                  <span>{text}</span>
                  {isCorrect && isPicked && <span className="review-tag">✅ You picked this (correct)</span>}
                  {isCorrect && !isPicked && <span className="review-tag">Correct answer</span>}
                  {isPicked && !isCorrect && <span className="review-tag">❌ Your answer</span>}
                </div>
              );
            })}
        </div>
      ) : (
        <p>
          Your answer: <strong>{entry.selectedAnswer}</strong> · Correct answer: <strong>{entry.correctAnswer}</strong>
        </p>
      )}

      <p className="muted" style={{ marginTop: "0.8rem" }}>
        {statusLabel} · {entry.masteryLabel} · skill {entry.skillScore.toFixed(2)}
      </p>
    </div>
  );
}