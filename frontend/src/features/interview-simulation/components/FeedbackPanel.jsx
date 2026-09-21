// src/features/interview-simulation/components/FeedbackPanel.jsx
export default function FeedbackPanel({ feedback, emotion }) {
  if (!feedback && !emotion) return null;
  return (
    <div className="feedback-panel">
      {feedback && (
        <>
          <h3>Feedback</h3>
          <p>{feedback}</p>
        </>
      )}
      {emotion && <p className="emotion-note">You appeared most: {emotion.dominant}</p>}
    </div>
  );
}