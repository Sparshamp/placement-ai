// src/features/interview-simulation/components/Hero.jsx
import heroImage from "../../../assets/interview-hero.png";

export default function Hero() {
  return (
    <section className="hero">
      <div className="hero-copy">
        <span className="eyebrow-badge">AI-POWERED PRACTICE</span>
        <h1>Practice interviews.<br />Build your confidence.</h1>
        <p className="hero-subhead">
          Upload your resume and a job description below to start a mock
          interview with real-time spoken questions and feedback.
        </p>
      </div>
      <div className="hero-art">
        <img src={heroImage} alt="Person practicing a video interview" />
      </div>
    </section>
  );
}