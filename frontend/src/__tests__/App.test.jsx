import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";

const QUESTIONS = {
  q1: {
    question_id: "q1", concept_id: "c1", canonical_subject: "General Aptitude",
    canonical_topic: "Logic", subtopic: "Puzzles", difficulty: "Easy",
    canonical_question_type: "mcq", question: "2+2=?",
    option_a: "3", option_b: "4", option_c: "5", option_d: "6", image_url: null,
  },
  q2: {
    question_id: "q2", concept_id: "c2", canonical_subject: "General Aptitude",
    canonical_topic: "Logic", subtopic: "Puzzles", difficulty: "Medium",
    canonical_question_type: "numerical", question: "What is 10/2?",
    option_a: null, option_b: null, option_c: null, option_d: null, image_url: null,
  },
  q3: {
    question_id: "q3", concept_id: "c3", canonical_subject: "Algorithms",
    canonical_topic: "Graph Algorithms", subtopic: "MST", difficulty: "Medium",
    canonical_question_type: "multi_select", question: "Which are true?",
    option_a: "Statement A", option_b: "Statement B", option_c: "Statement C", option_d: "Statement D",
    image_url: null,
  },
};
const ANSWERS = { q1: "B", q2: "5", q3: "A;C" };

function splitMulti(raw) {
  return new Set(String(raw || "").split(";").map((s) => s.trim().toUpperCase()).filter(Boolean));
}

function mockFetch(url, opts) {
  const u = new URL(url);
  const path = u.pathname;
  const method = opts?.method || "GET";

  if (path === "/") return jsonResponse({ status: "running" });
  if (path === "/practice-categories") return jsonResponse({ practice_categories: ["Aptitude", "MultiSelectTest"] });

  if (path === "/session/start" && method === "POST") {
    const body = JSON.parse(opts.body);
    if (body.practice_category === "MultiSelectTest") {
      return jsonResponse({
        session_id: "sess-2", student_id: "student1", practice_category: "MultiSelectTest",
        questions: [QUESTIONS.q3], count: 1,
      });
    }
    return jsonResponse({
      session_id: "sess-1", student_id: "student1", practice_category: "Aptitude",
      questions: [QUESTIONS.q1], count: 1,
    });
  }

  if (path === "/question/answer" && method === "POST") {
    const body = JSON.parse(opts.body);
    const qtype = QUESTIONS[body.question_id]?.canonical_question_type;
    let correct, answer_detail = null;
    if (qtype === "multi_select") {
      const correctSet = splitMulti(ANSWERS[body.question_id]);
      const selectedSet = splitMulti(body.selected_answer);
      correct = selectedSet.size === correctSet.size && [...selectedSet].every((x) => correctSet.has(x));
      const status = correct ? "correct" : [...selectedSet].some((x) => correctSet.has(x)) ? "partial" : "incorrect";
      answer_detail = {
        type: "multi_select", status,
        correct_options: [...correctSet].sort(),
        selected_options: [...selectedSet].sort(),
        missed_options: [...correctSet].filter((x) => !selectedSet.has(x)).sort(),
        extra_options: [...selectedSet].filter((x) => !correctSet.has(x)).sort(),
      };
    } else {
      correct = body.selected_answer.trim().toUpperCase() === ANSWERS[body.question_id].toUpperCase();
    }
    const next = body.question_id === "q1" ? QUESTIONS.q2 : body.question_id === "q3" ? QUESTIONS.q1 : null;
    return jsonResponse({
      correct, correct_answer: ANSWERS[body.question_id], answer_detail,
      updated_skill: {
        concept_id: body.concept_id, topic: body.topic, subtopic: body.subtopic,
        bkt_score: 0.5, ema_score: 0.5, skill_score: correct ? 0.55 : 0.25,
        mastery_label: correct ? "Proficient 🟡" : "Needs Practice 🔴", attempts: 1,
      },
      next_question: next,
    });
  }

  if (path.match(/^\/student\/.+\/summary$/)) {
    return jsonResponse({
      student_id: "student1",
      subjects: [
        { subject: "General Aptitude", concepts_seen: 2, avg_mastery: 0.4, mastered_count: 0, total_attempts: 2, accuracy: 0.5 },
      ],
    });
  }

  if (path.match(/^\/student\/.+\/skills$/)) {
    return jsonResponse({
      student_id: "student1", subject: "General Aptitude",
      coverage: { total_concepts: 10, concepts_seen: 2, concepts_mastered: 0, coverage_pct: 20.0, mastery_pct: 0.0 },
      skills: [{ concept_id: "c1", topic: "Logic", subtopic: "Puzzles", skill_score: 0.55, attempts: 1, correct_count: 1 }],
    });
  }

  if (path.match(/^\/student\/.+\/history$/)) {
    return jsonResponse({ student_id: "student1", history: [] });
  }

  return jsonResponse({ detail: "not found" }, 404);
}

function jsonResponse(body, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    statusText: String(status),
    json: () => Promise.resolve(body),
  });
}

beforeEach(() => {
  localStorage.setItem("apiBase", "http://localhost:8000");
  vi.stubGlobal("fetch", vi.fn(mockFetch));
  // BrowserRouter reads the real window.location, which jsdom does NOT
  // reset between tests in the same file -- without this, a test that
  // runs after the Dashboard test (which navigates to /dashboard) would
  // render App() already on /dashboard instead of the Practice home page.
  window.history.pushState({}, "", "/");
});

describe("Adaptive Aptitude combined flow", () => {
  it("renders Home/Practice page and shows connection status (collapsed sidebar by default)", async () => {
    render(<App />);
    await waitFor(() => expect(document.querySelector('[title="Connected"]')).toBeInTheDocument());
    expect(screen.getByText("Start a session")).toBeInTheDocument();
    // No backend URL / dev config is ever shown in the UI
    expect(screen.queryByLabelText("Backend URL")).not.toBeInTheDocument();
  });

  it("expands the sidebar on toggle click, revealing nav labels and status text (no backend URL)", async () => {
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(document.querySelector('[title="Connected"]')).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "Expand sidebar" }));
    expect(await screen.findByText("Connected")).toBeInTheDocument();
    expect(screen.queryByLabelText("Backend URL")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Collapse sidebar" }));
    expect(screen.queryByLabelText("Backend URL")).not.toBeInTheDocument();
  });

  it("loads practice categories from the backend", async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Aptitude" })).toBeInTheDocument());
  });

  it("runs a full session: pick category, answer MCQ, chain to numerical question, reach summary", async () => {
    const user = userEvent.setup();
    render(<App />);

    await waitFor(() => expect(screen.getByRole("button", { name: "Aptitude" })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Aptitude" }));

    const slider = screen.getByRole("slider");
    Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set.call(slider, "2");
    slider.dispatchEvent(new Event("input", { bubbles: true }));

    await user.click(screen.getByRole("button", { name: "Start Session" }));

    // Question 1: MCQ
    await waitFor(() => expect(screen.getByText("2+2=?")).toBeInTheDocument());
    await user.click(screen.getByText("4")); // option B
    await user.click(screen.getByRole("button", { name: "Submit Answer" }));

    // Chained next_question: numerical type
    await waitFor(() => expect(screen.getByText("What is 10/2?")).toBeInTheDocument());
    const answerBox = screen.getByLabelText("Your answer");
    await user.type(answerBox, "5");
    await user.click(screen.getByRole("button", { name: "Submit Answer" }));

    // Session summary
    await waitFor(() => expect(screen.getByText("📋 Session Summary")).toBeInTheDocument());
    expect(screen.getByText("2")).toBeInTheDocument(); // questions answered
  });

  it("Dashboard: clicking a subject expands its detail panel, clicking again collapses it", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("link", { name: /Dashboard/i }));
    await waitFor(() => expect(screen.getAllByText("General Aptitude").length).toBeGreaterThan(0));

    const subjectBtn = screen.getAllByRole("button", { name: "General Aptitude" })[0];

    // Expand: skill detail table appears (concept_id column value)
    await user.click(subjectBtn);
    await waitFor(() => expect(screen.getByText("c1")).toBeInTheDocument());

    // Collapse: clicking the SAME subject again hides it
    await user.click(subjectBtn);
    await waitFor(() => expect(screen.queryByText("c1")).not.toBeInTheDocument());
  });

  it("multi_select: renders checkboxes, allows a partial selection, and shows partial-credit feedback", async () => {
    const user = userEvent.setup();
    render(<App />);

    await waitFor(() => expect(screen.getByRole("button", { name: "MultiSelectTest" })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "MultiSelectTest" }));
    await user.click(screen.getByRole("button", { name: "Start Session" }));

    await waitFor(() => expect(screen.getByText("Which are true?")).toBeInTheDocument());
    expect(screen.getByText("Select all that apply.")).toBeInTheDocument();

    // Checkboxes, not radio buttons
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(4);

    // Correct answer is A;C -- select only A (a strict subset -> "partial")
    await user.click(screen.getByText("Statement A"));
    await user.click(screen.getByRole("button", { name: "Submit Answer" }));

    await waitFor(() => expect(screen.getByText(/Partially correct/)).toBeInTheDocument());
    expect(screen.getByText(/Missed: C/)).toBeInTheDocument();
  });
});