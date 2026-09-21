import { useState, useEffect } from "react";
import { apiGet, apiPost, ApiError } from "./api";
import QuestionCard from "./components/QuestionCard";
import MasteryRing from "./components/MasteryRing";
import ReviewPanel from "./components/ReviewPanel";
import { useAuth } from "../../shared/auth/AuthContext";

export default function Practice() {
  const [categories, setCategories] = useState([]);
  const { student } = useAuth();
  const studentId = student?.student_id;
  const [practiceCategory, setPracticeCategory] = useState(null);
  const [targetQuestions, setTargetQuestions] = useState(10);
  const [loadError, setLoadError] = useState(null);

  const [sessionId, setSessionId] = useState(null);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [questionShownAt, setQuestionShownAt] = useState(null);
  const [answersLog, setAnswersLog] = useState([]);
  const [feedback, setFeedback] = useState(null);
  const [sessionEnded, setSessionEnded] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiGet("/practice-categories")
      .then((data) => setCategories(data.practice_categories))
      .catch((e) => setLoadError(e.detail || e.message));
  }, []);

  const inActiveSession = sessionId !== null && !sessionEnded;

  function resetToHome() {
    setSessionId(null);
    setCurrentQuestion(null);
    setSessionEnded(false);
    setAnswersLog([]);
    setFeedback(null);
    setReviewing(false);
  }

  async function startSession() {
    setBusy(true);
    setLoadError(null);
    try {
      // Only request ONE question here -- see module docstring. Every
      // question after this is chosen via next_question in the answer
      // response, which is computed AFTER mastery updates from the
      // previous answer, so it's the only path that's genuinely adaptive
      // question-by-question. The initial batch would otherwise be
      // pre-selected before the student answered anything.
      const result = await apiPost("/session/start", {
        student_id: studentId,
        practice_category: practiceCategory,
        num_questions: 1,
      });
      setSessionId(result.session_id);
      setCurrentQuestion(result.questions[0]);
      setQuestionShownAt(Date.now());
      setAnswersLog([]);
      setSessionEnded(false);
      setFeedback(null);
    } catch (e) {
      setLoadError(e instanceof ApiError ? e.detail : e.message);
    } finally {
      setBusy(false);
    }
  }

  async function submitAnswer(selectedAnswer) {
    const q = currentQuestion;
    const elapsedSec = (Date.now() - questionShownAt) / 1000;
    setBusy(true);
    setLoadError(null);
    try {
      const result = await apiPost("/question/answer", {
        student_id: studentId,
        session_id: sessionId,
        practice_category: practiceCategory,
        question_id: q.question_id,
        concept_id: q.concept_id,
        subject: q.canonical_subject,
        topic: q.canonical_topic,
        subtopic: q.subtopic,
        difficulty: q.difficulty,
        selected_answer: selectedAnswer,
        time_taken_sec: Math.round(elapsedSec * 10) / 10,
      });

      const entry = {
        canonicalSubject: q.canonical_subject,
        canonicalTopic: q.canonical_topic,
        conceptId: q.concept_id,
        difficulty: q.difficulty,
        questionText: q.question,
        questionType: q.canonical_question_type || "mcq",
        options: { A: q.option_a, B: q.option_b, C: q.option_c, D: q.option_d },
        selectedAnswer,
        correctAnswer: result.correct_answer,
        correct: result.correct,
        answerDetail: result.answer_detail || null,
        skillScore: result.updated_skill.skill_score,
        masteryLabel: result.updated_skill.mastery_label,
      };
      const newLog = [...answersLog, entry];
      setAnswersLog(newLog);
      setFeedback(result);

      if (newLog.length >= targetQuestions || !result.next_question) {
        setSessionEnded(true);
        setCurrentQuestion(null);
      } else {
        setCurrentQuestion(result.next_question);
        setQuestionShownAt(Date.now());
      }
    } catch (e) {
      setLoadError(e instanceof ApiError ? e.detail : e.message);
    } finally {
      setBusy(false);
    }
  }

  async function skipQuestion() {
    setBusy(true);
    try {
      const q = await apiGet("/question/next", {
        student_id: studentId,
        practice_category: practiceCategory,
      });
      setCurrentQuestion(q);
      setQuestionShownAt(Date.now());
    } catch (e) {
      setSessionEnded(true);
      setCurrentQuestion(null);
    } finally {
      setBusy(false);
    }
  }

  // ---- Render: session summary ----
  if (sessionEnded) {
    const n = answersLog.length;
    const correct = answersLog.filter((a) => a.correct).length;
    return (
      <div className="page-narrow">
        <h2>📋 Session Summary</h2>
        {n === 0 ? (
          <p className="muted">No questions were answered this session.</p>
        ) : (
          <>
            <div className="summary-stats">
              <div className="stat card"><span className="stat-value">{n}</span><span className="muted">Questions answered</span></div>
              <div className="stat card"><span className="stat-value">{correct}/{n}</span><span className="muted">Correct</span></div>
              <div className="stat card"><span className="stat-value">{Math.round((correct / n) * 100)}%</span><span className="muted">Accuracy</span></div>
            </div>
            <table className="data-table">
              <thead>
                <tr><th>Subject</th><th>Topic</th><th>Result</th><th>Skill</th><th>Mastery</th></tr>
              </thead>
              <tbody>
                {answersLog.map((a, i) => {
                  const status = a.answerDetail?.status || (a.correct ? "correct" : "incorrect");
                  const icon = { correct: "✅", partial: "🟡", incorrect: "❌" }[status];
                  return (
                    <tr key={i}>
                      <td>{a.canonicalSubject}</td>
                      <td>{a.canonicalTopic}</td>
                      <td>{icon}</td>
                      <td className="mono">{a.skillScore.toFixed(2)}</td>
                      <td>{a.masteryLabel}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </>
        )}
        <button className="primary" onClick={resetToHome} style={{ marginTop: "1rem" }}>
          Start another session
        </button>
      </div>
    );
  }

  // ---- Render: category picker ----
  if (!inActiveSession) {
    return (
      <div className="page-narrow">
        <h2>Start a session</h2>
        {loadError && <p className="warning-text">{loadError}</p>}

        <p className="muted">Practicing as {student?.display_name}</p>

        <p className="muted" style={{ marginTop: "1.2rem" }}>Practice category</p>
        <div className="category-grid">
          {categories.map((cat) => (
            <button
              key={cat}
              className={practiceCategory === cat ? "primary" : ""}
              onClick={() => setPracticeCategory(cat)}
            >
              {practiceCategory === cat ? "✅ " : ""}{cat}
            </button>
          ))}
        </div>

        <label className="muted" style={{ marginTop: "1.2rem", display: "block" }}>
          Questions this session: {targetQuestions}
        </label>
        <input
          type="range" min="5" max="30" value={targetQuestions}
          onChange={(e) => setTargetQuestions(Number(e.target.value))}
          style={{ width: "100%" }}
        />

        <button
          className="primary"
          style={{ marginTop: "1.2rem" }}
          disabled={!studentId || !practiceCategory || busy}
          onClick={startSession}
        >
          Start Session
        </button>
      </div>
    );
  }

  // ---- Render: active session ----
  const nDone = answersLog.length;

  if (reviewing) {
    return (
      <div className="page-wide">
        <ReviewPanel log={answersLog} onClose={() => setReviewing(false)} />
      </div>
    );
  }

  return (
    <div className="page-wide">
      <div className="progress-row">
        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${Math.min((nDone / targetQuestions) * 100, 100)}%` }} />
        </div>
        <span className="muted mono">Q{nDone + 1} of {targetQuestions}</span>
      </div>

      <div className="session-toolbar">
        {nDone > 0 && (
          <button className="subtle" onClick={() => setReviewing(true)}>📖 Previous Questions ({nDone})</button>
        )}
        <button className="subtle" onClick={resetToHome}>🏠 Home</button>
      </div>
      {inActiveSession && (
        <p className="faint" style={{ marginTop: "-0.4rem" }}>
          ⚠️ Leaves your current question unanswered (already-submitted answers stay saved).
        </p>
      )}

      {feedback && (() => {
        const status = feedback.answer_detail?.status || (feedback.correct ? "correct" : "incorrect");
        const bannerClass =
          status === "correct" ? "feedback-banner--correct"
          : status === "partial" ? "feedback-banner--partial"
          : "feedback-banner--incorrect";
        const readableCorrect = String(feedback.correct_answer || "").split(";").join(", ");
        return (
          <div className={`feedback-banner ${bannerClass}`}>
            <MasteryRing skillScore={feedback.updated_skill.skill_score} size={44} />
            <div>
              <strong>
                {status === "correct" && "✅ Correct!"}
                {status === "partial" && `🟡 Partially correct. Correct answer: ${readableCorrect}`}
                {status === "incorrect" && `❌ Incorrect. Correct answer: ${readableCorrect}`}
              </strong>
              {feedback.answer_detail && (
                <div className="muted" style={{ fontSize: "0.85rem" }}>
                  You selected: {feedback.answer_detail.selected_options.join(", ") || "(none)"}
                  {feedback.answer_detail.missed_options.length > 0 &&
                    ` · Missed: ${feedback.answer_detail.missed_options.join(", ")}`}
                  {feedback.answer_detail.extra_options.length > 0 &&
                    ` · Incorrectly selected: ${feedback.answer_detail.extra_options.join(", ")}`}
                </div>
              )}
              <div className="muted">{feedback.updated_skill.mastery_label} · skill {feedback.updated_skill.skill_score.toFixed(2)}</div>
            </div>
          </div>
        );
      })()}

      {loadError && <p className="warning-text">{loadError}</p>}

      {currentQuestion ? (
        <QuestionCard
          question={currentQuestion}
          onSubmit={submitAnswer}
          onSkip={skipQuestion}
        />
      ) : (
        <p className="muted">No more suitable questions available in this category right now.</p>
      )}

      <button className="subtle" style={{ marginTop: "1rem" }} onClick={() => setSessionEnded(true)}>
        End session early
      </button>
    </div>
  );
}