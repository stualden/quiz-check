import csv
import math
from collections import defaultdict

EVENTS_FILE = "events.csv"
METRICS_FILE = "metrics.csv"
OUTPUT_FILE = "summary.txt"

# ----------------------------
# Helpers
# ----------------------------

def clamp(x, lo, hi):
    return max(lo, min(hi, x))


# ----------------------------
# Load data
# ----------------------------

def load_events():
    data = defaultdict(list)

    with open(EVENTS_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sid = row["student_id"]
            t = int(row["time_sec"])
            e = row["event"]
            data[sid].append((t, e))

    return data


def load_metrics():
    data = {}

    with open(METRICS_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sid = row["student_id"]
            data[sid] = {k: float(v) if k != "student_id" else v for k, v in row.items()}

    return data


# ----------------------------
# Pattern detection
# ----------------------------

def detect_patterns(events):
    """
    Detect:
    - bursts (clusters of fast answers)
    - pause -> burst patterns
    """

    # extract answer times
    answer_times = [t for t, e in events if e == "ANSWER"]

    if len(answer_times) < 3:
        return {
            "burst_sequences": 0,
            "pause_burst_patterns": 0
        }

    gaps = [
        answer_times[i+1] - answer_times[i]
        for i in range(len(answer_times) - 1)
    ]

    mean_gap = sum(gaps) / len(gaps)

    long_thresh = mean_gap * 2
    short_thresh = mean_gap * 0.5

    burst_sequences = 0
    pause_burst_patterns = 0

    i = 0
    while i < len(gaps):

        # detect burst (2+ short gaps in a row)
        if gaps[i] < short_thresh:
            start = i
            count = 1

            while i + 1 < len(gaps) and gaps[i + 1] < short_thresh:
                i += 1
                count += 1

            if count >= 2:
                burst_sequences += 1

                # check if preceded by long pause
                if start > 0 and gaps[start - 1] > long_thresh:
                    pause_burst_patterns += 1

        i += 1

    return {
        "burst_sequences": burst_sequences,
        "pause_burst_patterns": pause_burst_patterns
    }


# ----------------------------
# Scoring
# ----------------------------

def compute_score(m, patterns):
    """
    FIXED scoring model:

    PRIORITY:
    1. Off-task behavior (dominant)
    2. Switching (secondary)
    3. Patterns ONLY if off-task present
    4. Timing/revisions = very weak signals

    Key safeguard:
    Clean students (no off-task) should stay ~1.0
    """

    duration = m["duration_sec"]

    off_time = m["total_off_time_sec"]
    off_ratio = off_time / duration if duration > 0 else 0

    switch_rate = m["switch_rate_per_min"]

    cv_gap = m["cv_gap"]
    burst_count = m["burst_count"]

    revision_ratio = m["revision_ratio"]
    max_rev = m["max_revisions_single_q"]

    burst_sequences = patterns["burst_sequences"]
    pause_burst = patterns["pause_burst_patterns"]

    # ----------------------------
    # BASE SCORE
    # ----------------------------
    score = 1.0

    # ----------------------------
    # STRONG SIGNALS
    # ----------------------------

    # Off-task time (primary driver)
    score += clamp(off_ratio * 3.0, 0, 2.0)

    # Switching (secondary)
    score += clamp(switch_rate * 0.15, 0, 0.75)

    # ----------------------------
    # GATING CONDITION
    # ----------------------------
    # If essentially no off-task behavior, suppress most penalties
    low_off_task = (off_ratio < 0.02 and switch_rate < 0.5)

    # ----------------------------
    # PATTERNS (ONLY if off-task present)
    # ----------------------------
    if not low_off_task:
        # normalize patterns relative to quiz length
        pattern_strength = pause_burst / 3.0  # dampen

        score += clamp(pattern_strength * 0.8, 0, 0.8)

    # ----------------------------
    # VERY WEAK SIGNALS
    # ----------------------------
    if not low_off_task:
        score += clamp(cv_gap * 0.15, 0, 0.3)
        score += clamp(burst_count * 0.03, 0, 0.3)

        score += clamp(revision_ratio * 0.5, 0, 0.2)
        score += clamp((max_rev - 1) * 0.05, 0, 0.2)

    # ----------------------------
    # FINAL CLAMP
    # ----------------------------
    return round(clamp(score, 1, 5), 2)

# ----------------------------
# Write summary
# ----------------------------

def write_summary(events_data, metrics_data):

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:

        for sid in sorted(metrics_data.keys()):
            m = metrics_data[sid]
            events = sorted(events_data[sid], key=lambda x: x[0])

            patterns = detect_patterns(events)
            score = compute_score(m, patterns)

            duration = m["duration_sec"]
            off_time = m["total_off_time_sec"]
            off_ratio = off_time / duration if duration > 0 else 0

            f.write(f"STUDENT {sid}\n")
            f.write("-" * 40 + "\n")

            f.write(f"Final Score: {score}\n\n")

            f.write("Core Behavior:\n")
            f.write(f"  Duration: {duration:.0f}s\n")
            f.write(f"  Off-task time: {off_time:.0f}s ({off_ratio:.2f})\n")
            f.write(f"  Switch rate: {m['switch_rate_per_min']:.2f}/min\n\n")

            f.write("Timing:\n")
            f.write(f"  Mean gap: {m['mean_gap_sec']:.2f}s\n")
            f.write(f"  Variability (CV): {m['cv_gap']:.2f}\n")
            f.write(f"  Long gaps: {m['long_gap_count']:.0f}\n")
            f.write(f"  Burst count: {m['burst_count']:.0f}\n\n")

            f.write("Patterns:\n")
            f.write(f"  Burst sequences: {patterns['burst_sequences']}\n")
            f.write(f"  Pause→Burst patterns: {patterns['pause_burst_patterns']}\n\n")

            f.write("Revisions:\n")
            f.write(f"  Revision ratio: {m['revision_ratio']:.2f}\n")
            f.write(f"  Max per question: {m['max_revisions_single_q']:.0f}\n\n")

            f.write("\n")


# ----------------------------
# Main
# ----------------------------

def main():
    events_data = load_events()
    metrics_data = load_metrics()

    write_summary(events_data, metrics_data)
    print("Summary written to summary.txt")


if __name__ == "__main__":
    main()
