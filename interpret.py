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
            data[sid] = {
                k: float(v) if k != "student_id" else v
                for k, v in row.items()
            }

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

        if gaps[i] < short_thresh:
            start = i
            count = 1

            while i + 1 < len(gaps) and gaps[i + 1] < short_thresh:
                i += 1
                count += 1

            if count >= 2:
                burst_sequences += 1

                if start > 0 and gaps[start - 1] > long_thresh:
                    pause_burst_patterns += 1

        i += 1

    return {
        "burst_sequences": burst_sequences,
        "pause_burst_patterns": pause_burst_patterns
    }


# ----------------------------
# Scoring (UNCHANGED)
# ----------------------------

def compute_score(m, patterns):

    duration = m["duration_sec"]

    off_time = m["total_off_time_sec"]
    off_ratio = off_time / duration if duration > 0 else 0

    switch_density = m["switch_density_per_min"]

    rapid_switches = m["rapid_switch_count"]
    long_switches = m["long_switch_count"]

    post_resume_ratio = m["post_resume_fast_ratio"]

    cv_gap = m["cv_gap"]
    burst_count = m["burst_count"]

    revision_ratio = m["revision_ratio"]
    max_rev = m["max_revisions_single_q"]

    pause_burst = patterns["pause_burst_patterns"]

    score = 1.0

    # primary
    score += clamp(off_ratio * 3.0, 0, 2.0)

    # secondary
    score += clamp(switch_density * 0.12, 0, 0.6)

    low_off_task = (off_ratio < 0.02 and switch_density < 0.5)

    if not low_off_task:
        score += clamp(post_resume_ratio * 1.5, 0, 1.5)
        score += clamp(rapid_switches * 0.08, 0, 0.5)
        score += clamp(long_switches * 0.05, 0, 0.4)
        score += clamp(pause_burst * 0.3, 0, 0.6)

    if not low_off_task:
        score += clamp(cv_gap * 0.12, 0, 0.3)
        score += clamp(burst_count * 0.02, 0, 0.25)
        score += clamp(revision_ratio * 0.4, 0, 0.2)
        score += clamp((max_rev - 1) * 0.04, 0, 0.2)

    return round(clamp(score, 1, 5), 2)


# ----------------------------
# Write summary (UPDATED TEXT)
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
            f.write("-" * 50 + "\n")

            f.write(f"Final Score: {score}\n\n")

            # ----------------------------
            # Core Behavior
            # ----------------------------
            f.write("Core Behavior:\n")
            f.write(f"  Duration: {duration:.0f}s\n")
            f.write(f"  Off-task time: {off_time:.0f}s ({off_ratio:.2f} of session)\n")
            f.write(f"  Number of switches: {m['off_switches']:.0f}\n")
            f.write(f"  Switch density: {m['switch_density_per_min']:.2f} per minute\n")
            f.write(f"  Rapid switches (≤5s away): {m['rapid_switch_count']:.0f}\n")
            f.write(f"  Long switches (≥15s away): {m['long_switch_count']:.0f}\n\n")

            # ----------------------------
            # Post-resume behavior
            # ----------------------------
            f.write("Post-Resume Behavior:\n")
            f.write(f"  Avg time to answer after returning: {m['post_resume_avg_sec']:.2f}s\n")
            f.write(f"  Fast answers after return (≤5s): {m['post_resume_fast_count']:.0f}\n")
            f.write(f"  Fast ratio: {m['post_resume_fast_ratio']:.2f} "
                    f"(fraction of returns followed by an answer within 5s)\n\n")

            # ----------------------------
            # Timing
            # ----------------------------
            f.write("Timing Between Answers:\n")
            f.write(f"  Mean gap: {m['mean_gap_sec']:.2f}s (average time between answering questions)\n")
            f.write(f"  Variability (CV): {m['cv_gap']:.2f} (higher = more uneven pacing)\n")
            f.write(f"  Long gaps: {m['long_gap_count']:.0f} (unusually slow responses)\n")
            f.write(f"  Burst count: {m['burst_count']:.0f} (very fast consecutive answers)\n\n")

            # ----------------------------
            # Patterns
            # ----------------------------
            f.write("Answering Patterns:\n")
            f.write(f"  Burst sequences: {patterns['burst_sequences']} "
                    f"(clusters of multiple rapid answers in a row)\n")
            f.write(f"  Pause→Burst patterns: {patterns['pause_burst_patterns']} "
                    f"(long pause followed by rapid answering — possible lookup behavior)\n\n")

            # ----------------------------
            # Revisions
            # ----------------------------
            f.write("Revisions:\n")
            f.write(f"  Revision ratio: {m['revision_ratio']:.2f} "
                    f"(fraction of answers that were changed)\n")
            f.write(f"  Max revisions on a single question: {m['max_revisions_single_q']:.0f}\n\n")

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
    