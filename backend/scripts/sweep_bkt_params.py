
"""
scripts/sweep_bkt_params.py
-------------------------------
Answers "what should I change SUBJECT_BKT_PARAMS to?" empirically instead
of by guessing. Runs BKTOnlySelector across a grid of (p_init, p_transit,
p_slip, p_guess) values -- using the override_params mechanism on
BKTOnlySelector -- against BOTH Step 3 simulators (BKTGenerativeSimulator,
IRTGenerativeSimulator), and recommends the combination that's good
across BOTH, not just whichever one has the single lowest number.

WHY "BEST" IS RANKED BY MEAN ACROSS BOTH SIMULATORS, NOT THE SINGLE BEST
ROW: picking whichever row has the single lowest calibration_error can
recommend a combination that's great on bkt_generative and terrible on
irt_generative (or vice versa) -- exactly the kind of overfitting-to-one-
simulator the whole two-simulator design exists to catch. Ranking by the
MEAN of both simulators' calibration_error (with the MAX shown alongside,
so you can see how much it still varies) recommends something that's
actually robust, not a fluke.

This does NOT edit core/knowledge_model.py's SUBJECT_BKT_PARAMS for you --
it's a measurement tool. It DOES print ready-to-paste dict entries for
every category swept, at the end, to make applying the result low-effort.

NOTE ON GRANULARITY: this sweeps one combination per PRACTICE CATEGORY,
applied uniformly to every canonical_subject inside it (override_params
replaces ALL subject-specific lookups for the run, see
BKTOnlySelector.__init__). For categories with multiple subjects (Core CS
has 13), the recommended combination is a reasonable starting point for
all of them, not an independently-tuned value per subject -- per-subject
tuning would need one sweep run per subject, which this script doesn't do
(would be 13x the runtime for Core CS alone; revisit only if the
category-wide value turns out not good enough).

Usage:
    # one category
    python scripts/sweep_bkt_params.py --practice-category "Engineering Mathematics" \
        --n-students 100 --n-questions 40

    # every category with logged questions in Postgres, one command
    python scripts/sweep_bkt_params.py --practice-category all --n-students 100 --n-questions 40

    # customize the grid (comma-separated values, all combinations tried)
    python scripts/sweep_bkt_params.py --practice-category all \
        --p-transit 0.05,0.10,0.15 --p-slip 0.08,0.15,0.20 --p-guess 0.15,0.25 --p-init 0.30

    # sweep against the concept-FOCUS selection policy instead of roaming --
    # use this once you've adopted *_focused as your reported algorithm,
    # since focus mode gives BKT far more repeated observations per concept
    # before moving on, which can shift which (p_transit, p_slip, p_guess)
    # combination actually calibrates best
    python scripts/sweep_bkt_params.py --practice-category all --focused --n-students 100 --n-questions 40
"""

import argparse
import itertools
import sys
import os
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from experiments.data import load_experiment_data  # noqa: E402
from experiments.selectors.mastery_based import BKTOnlySelector, BKTOnlyFocusedSelector  # noqa: E402
from experiments.simulators import BKTGenerativeSimulator, IRTGenerativeSimulator  # noqa: E402
from experiments.runner import ExperimentConfig, run_experiment  # noqa: E402
from core.knowledge_model import BKTParams  # noqa: E402


def parse_floats(s):
    return [float(x) for x in s.split(",")]


def sweep_one_category(category: str, combos, args, questions_df, dag, selector_cls):
    print(f"\n{'#' * 100}\n# practice_category={category!r} -- {len(combos)} combos x 2 simulators "
          f"({len(combos) * 2} total runs)\n{'#' * 100}")

    simulators = {
        "bkt_generative": lambda: BKTGenerativeSimulator(seed=args.seed),
        "irt_generative": lambda: IRTGenerativeSimulator(seed=args.seed),
    }

    rows = []
    for p_init, p_transit, p_slip, p_guess in combos:
        params = BKTParams(p_init=p_init, p_transit=p_transit, p_slip=p_slip, p_guess=p_guess)
        for sim_name, sim_factory in simulators.items():
            selector = selector_cls(override_params=params)
            simulator = sim_factory()
            config = ExperimentConfig(
                practice_category=category,
                n_students=args.n_students,
                n_questions_per_student=args.n_questions,
                log_to_db=not args.no_db,
            )
            try:
                result = run_experiment(selector, simulator, questions_df, dag, config)
            except ValueError as e:
                print(f"SKIPPED {params} / {sim_name}: {e}")
                continue
            m = result["metrics"]
            rows.append({
                "p_init": p_init, "p_transit": p_transit, "p_slip": p_slip, "p_guess": p_guess,
                "simulator": sim_name,
                "roc_auc": m["roc_auc"], "brier_score": m["brier_score"],
                "log_loss": m["log_loss"], "calibration_error": m["calibration_error"],
            })

    if not rows:
        print(f"No results for {category!r} -- skipping.")
        return None

    # group by param combo across BOTH simulators, rank by MEAN calibration_error
    by_combo = defaultdict(list)
    for r in rows:
        key = (r["p_init"], r["p_transit"], r["p_slip"], r["p_guess"])
        by_combo[key].append(r)

    combo_summaries = []
    for key, combo_rows in by_combo.items():
        if len(combo_rows) < 2:
            continue  # skip combos that didn't complete both simulators -- not a fair comparison
        mean_calib = sum(r["calibration_error"] for r in combo_rows) / len(combo_rows)
        max_calib = max(r["calibration_error"] for r in combo_rows)
        mean_roc = sum(r["roc_auc"] for r in combo_rows) / len(combo_rows)
        combo_summaries.append({
            "p_init": key[0], "p_transit": key[1], "p_slip": key[2], "p_guess": key[3],
            "mean_calibration_error": mean_calib, "max_calibration_error": max_calib,
            "mean_roc_auc": mean_roc,
        })
    combo_summaries.sort(key=lambda r: r["mean_calibration_error"])

    print(f"\nTop 5 combos for {category!r}, ranked by MEAN calibration_error across both simulators:")
    print(f"{'p_init':<8}{'p_transit':<11}{'p_slip':<9}{'p_guess':<9}"
          f"{'mean_calib':<12}{'max_calib':<12}{'mean_roc_auc':<14}")
    for s in combo_summaries[:5]:
        print(f"{s['p_init']:<8.2f}{s['p_transit']:<11.2f}{s['p_slip']:<9.2f}{s['p_guess']:<9.2f}"
              f"{s['mean_calibration_error']:<12.4f}{s['max_calibration_error']:<12.4f}{s['mean_roc_auc']:<14.4f}")

    return combo_summaries[0] if combo_summaries else None


def main():
    parser = argparse.ArgumentParser(description="Sweep BKT parameters against Step 3 simulators")
    parser.add_argument("--practice-category", required=True,
                         help='e.g. "Engineering Mathematics", or "all" to sweep every category in one run')
    parser.add_argument("--p-init", default="0.30")
    parser.add_argument("--p-transit", default="0.05,0.10,0.15")
    parser.add_argument("--p-slip", default="0.08,0.15,0.20")
    parser.add_argument("--p-guess", default="0.15,0.20,0.25")
    parser.add_argument("--n-students", type=int, default=100)
    parser.add_argument("--n-questions", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-db", action="store_true")
    parser.add_argument("--focused", action="store_true",
                         help="Sweep against BKTOnlyFocusedSelector (stays on one concept until "
                              "mastered/exhausted) instead of BKTOnlySelector (roaming, one concept "
                              "per question). Use this once you've switched to the focused policy in "
                              "production/reporting -- params tuned against roaming won't necessarily "
                              "still be optimal, since focused mode gives BKT far more repeated "
                              "observations per concept before moving on.")
    args = parser.parse_args()

    p_inits = parse_floats(args.p_init)
    p_transits = parse_floats(args.p_transit)
    p_slips = parse_floats(args.p_slip)
    p_guesses = parse_floats(args.p_guess)
    combos = list(itertools.product(p_inits, p_transits, p_slips, p_guesses))

    category_filter = None if args.practice_category == "all" else args.practice_category
    questions_df, dag = load_experiment_data(practice_category=category_filter)
    categories = (
        sorted(questions_df["practice_category"].dropna().unique().tolist())
        if args.practice_category == "all"
        else [args.practice_category]
    )

    best_per_category = {}
    selector_cls = BKTOnlyFocusedSelector if args.focused else BKTOnlySelector
    print(f"\nSweeping against: {selector_cls.__name__}"
          f"{' (concept-focus policy)' if args.focused else ' (roaming policy)'}")

    for category in categories:
        best = sweep_one_category(category, combos, args, questions_df, dag, selector_cls)
        if best:
            best_per_category[category] = best

    if len(categories) > 1:
        print(f"\n{'=' * 100}\nSUMMARY -- best combo per category (mean calibration_error across both simulators)\n{'=' * 100}")
        for category, best in best_per_category.items():
            print(f"  {category:<35} mean_calib={best['mean_calibration_error']:.4f}  "
                  f"max_calib={best['max_calibration_error']:.4f}  mean_roc_auc={best['mean_roc_auc']:.4f}")

    print(f"\n{'=' * 100}\nREADY TO PASTE into SUBJECT_BKT_PARAMS in core/knowledge_model.py\n{'=' * 100}")
    print("(apply to every canonical_subject in that category -- see module docstring on granularity)\n")
    for category, best in best_per_category.items():
        print(f'    # {category} -- swept mean_calib={best["mean_calibration_error"]:.4f} '
              f'(max across sims: {best["max_calibration_error"]:.4f})')
        print(f'    # BKTParams({best["p_init"]:.2f}, {best["p_transit"]:.2f}, '
              f'{best["p_slip"]:.2f}, {best["p_guess"]:.2f})')


if __name__ == "__main__":
    main()
