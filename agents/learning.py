"""Learning Agent.

Mechanism: chooses actions from EXPERIENCE (success/failure counts per
situation), and updates that experience when an outcome is recorded.

Components (textbook learning-agent structure):
  - Performance element: classify the situation, pick the action with the
    highest estimated success rate (Laplace-smoothed: (s+1)/(s+f+2)).
  - Critic: record_outcome() receives whether the action worked.
  - Learning element: updates the counts in data/experience.json.
  - Problem generator: points out under-tried actions worth testing.

data/experience_seed.json holds the starting history; data/experience.json is
the live copy that gets updated (delete it, or call reset(), to start over).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from agents.base import Decision
from agents.percepts import extract_percepts

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MIN_TRIALS_FOR_CONFIDENCE = 5


def classify_situation(p: dict) -> str:
    if not p["record_consistent"]:
        return "record_conflict"
    if p["reports_not_received"] and p["status"] == "delivered":
        return "delivered_not_received"
    if p["refund_overdue"]:
        return "refund_overdue"
    if p["refund_pending"]:
        return "refund_pending"
    if p["tracking_stalled"]:
        return "tracking_stalled"
    if p["status"] == "in_transit":
        return "in_transit"
    return "other"


def success_rate(stats: dict) -> float:
    return (stats["success"] + 1) / (stats["success"] + stats["failure"] + 2)


class LearningAgent:
    name = "Learning"
    mechanism = "Picks the action with the best success rate in past experience; updates counts from outcomes"

    def __init__(self, experience_path: Path | None = None, seed_path: Path | None = None):
        self.seed_path = Path(seed_path or DATA_DIR / "experience_seed.json")
        self.path = Path(experience_path or DATA_DIR / "experience.json")
        if not self.path.exists():
            self.reset()

    # ---- experience storage -------------------------------------------------
    def reset(self) -> None:
        shutil.copyfile(self.seed_path, self.path)

    def load(self) -> dict:
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def save(self, experience: dict) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(experience, f, indent=2)

    # ---- critic + learning element -------------------------------------------
    def record_outcome(self, situation: str, action: str, success: bool) -> dict:
        exp = self.load()
        stats = exp.setdefault(situation, {}).setdefault(action, {"success": 0, "failure": 0})
        stats["success" if success else "failure"] += 1
        self.save(exp)
        return stats

    # ---- performance element + problem generator ----------------------------
    def decide(self, case: dict) -> Decision:
        p = extract_percepts(case)
        situation = classify_situation(p)
        history = self.load().get(situation, {})
        r = [f"Situation classified as '{situation}'."]

        if not history:
            r.append("No past experience for this situation -> escalate and learn from the outcome.")
            return Decision(self.name, self.mechanism, "escalate_to_human", r,
                            {"situation": situation, "experience": {}}, r[-1])

        table = {a: {**s, "trials": s["success"] + s["failure"],
                     "success_rate": round(success_rate(s), 3)} for a, s in history.items()}
        best = max(table, key=lambda a: table[a]["success_rate"])
        for a, t in sorted(table.items(), key=lambda kv: -kv[1]["success_rate"]):
            r.append(f"{a}: {t['success']} successes / {t['failure']} failures "
                     f"-> estimated success {t['success_rate']:.0%}.")
        r.append(f"Chose {best} because it has the highest success rate in past cases.")

        under_tried = [a for a, t in table.items() if t["trials"] < MIN_TRIALS_FOR_CONFIDENCE]
        if table[best]["trials"] < MIN_TRIALS_FOR_CONFIDENCE:
            r.append(f"Caution: only {table[best]['trials']} trials for the chosen action.")
        if under_tried:
            r.append(f"Problem generator: under-tried actions worth testing: {under_tried}.")
        r.append("Recording a success or failure for this case will update these counts.")
        return Decision(self.name, self.mechanism, best, r,
                        {"situation": situation, "experience": table,
                         "under_tried": under_tried},
                        f"{situation}: {best} succeeded {table[best]['success']}/{table[best]['trials']} times "
                        f"(est. {table[best]['success_rate']:.0%})")
