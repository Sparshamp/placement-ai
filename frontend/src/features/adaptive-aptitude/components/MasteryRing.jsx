import "./MasteryRing.css";

const MASTERY_THRESHOLD = 0.75; // matches core/question_selector.py mastery_threshold_mastered

/**
 * Circular indicator showing how close the CURRENT concept is to the
 * backend's actual mastery threshold (0.75), not a generic progress bar.
 * skill_score is the same 0.6*bkt + 0.4*ema blend the backend computes.
 */
export default function MasteryRing({ skillScore = 0.3, size = 64 }) {
  const pct = Math.min(skillScore / MASTERY_THRESHOLD, 1);
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - pct);
  const mastered = skillScore >= MASTERY_THRESHOLD;

  return (
    <div className="mastery-ring" style={{ width: size, height: size }} title={`Skill score ${skillScore.toFixed(2)} / mastery at ${MASTERY_THRESHOLD}`}>
      <svg width={size} height={size}>
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          className="mastery-ring-track"
        />
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          className={mastered ? "mastery-ring-fill mastery-ring-fill--done" : "mastery-ring-fill"}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <span className="mastery-ring-label">{mastered ? "✓" : skillScore.toFixed(2)}</span>
    </div>
  );
}
