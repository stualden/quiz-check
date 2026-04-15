import re
import csv

INPUT_FILE = "logs.txt"
EVENTS_OUT = "events.csv"
METRICS_OUT = "metrics.csv"

# ----------------------------
# Helpers
# ----------------------------

def parse_time(t):
    """Convert MM:SS into seconds"""
    m, s = t.strip().split(":")
    return int(m) * 60 + int(s)

def chunk_students(text):
    """Split raw file into student blocks"""
    parts = text.split("Skip To Quiz Content")
    return [p.strip() for p in parts if p.strip()]

# ----------------------------
# Main
# ----------------------------

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    raw = f.read()

students = chunk_students(raw)

event_rows = []
metric_rows = []

student_id = 1

for block in students:
    sid = f"{student_id:02d}"
    student_id += 1

    lines = block.splitlines()

    events = []
    off_times = []
    answer_times = []

    # revision tracking
    question_counts = {}
    total_answers = 0

    last_stop_time = None
    current_time = None

    # ----------------------------
    # Parse events
    # ----------------------------

    for line in lines:
        line = line.strip()

        # time line
        match_time = re.match(r"^(\d{1,2}:\d{2})$", line)
        if match_time:
            current_time = parse_time(match_time.group(1))
            continue

        if current_time is None:
            continue

        # STOP
        if "Stopped viewing the quiz-taking page" in line:
            last_stop_time = current_time
            events.append((sid, current_time, "STOP"))

        # RESUME
        elif "Resumed" in line and last_stop_time is not None:
            resumed_time = current_time
            events.append((sid, current_time, "RESUME"))

            off_duration = resumed_time - last_stop_time
            if off_duration >= 0:
                off_times.append(off_duration)

            last_stop_time = None

        # ANSWER
        elif "Answered question" in line:
            events.append((sid, current_time, "ANSWER"))
            answer_times.append(current_time)

            # extract question number
            m_q = re.search(r"Answered question (\d+)", line)
            if m_q:
                qnum = int(m_q.group(1))
                question_counts[qnum] = question_counts.get(qnum, 0) + 1
                total_answers += 1

        # session end marker (used for duration)
        elif "Session submitted" in line:
            events.append((sid, current_time, "SUBMIT"))

    # ----------------------------
    # Metrics
    # ----------------------------

    # duration
    if events:
        times = [e[1] for e in events]
        duration = max(times) - min(times)
    else:
        duration = 0

    # off-task metrics
    num_switches = len(off_times)
    total_off = sum(off_times)
    avg_off = total_off / num_switches if num_switches else 0

    if len(off_times) > 1:
        mean_off = avg_off
        variance = sum((x - mean_off) ** 2 for x in off_times) / len(off_times)
    else:
        variance = 0

    switch_rate = num_switches / (duration / 60) if duration > 0 else 0

    # ----------------------------
    # Timing metrics
    # ----------------------------

    gaps = [
        answer_times[i+1] - answer_times[i]
        for i in range(len(answer_times) - 1)
    ]

    if gaps:
        mean_gap = sum(gaps) / len(gaps)
        std_gap = (sum((g - mean_gap) ** 2 for g in gaps) / len(gaps)) ** 0.5
        cv_gap = std_gap / mean_gap if mean_gap > 0 else 0

        # thresholds
        long_gap_threshold = mean_gap * 2
        burst_threshold = mean_gap * 0.5

        long_gap_count = sum(1 for g in gaps if g > long_gap_threshold)
        burst_count = sum(1 for g in gaps if g < burst_threshold)
    else:
        mean_gap = std_gap = cv_gap = 0
        long_gap_count = burst_count = 0

    # ----------------------------
    # Revision metrics
    # ----------------------------

    unique_questions = len(question_counts)

    revisions = sum(
        count - 1 for count in question_counts.values()
        if count > 1
    )

    revision_ratio = revisions / total_answers if total_answers else 0
    max_revisions = max(question_counts.values()) if question_counts else 0

    # ----------------------------
    # Store metrics
    # ----------------------------

    metric_rows.append([
        sid,
        duration,
        num_switches,
        total_off,
        avg_off,
        variance,
        switch_rate,
        mean_gap,
        std_gap,
        cv_gap,
        long_gap_count,
        burst_count,
        total_answers,
        unique_questions,
        revisions,
        revision_ratio,
        max_revisions
    ])

    event_rows.extend(events)

# ----------------------------
# Write CSVs
# ----------------------------

with open(EVENTS_OUT, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["student_id", "time_sec", "event"])
    writer.writerows(event_rows)

with open(METRICS_OUT, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "student_id",
        "duration_sec",
        "off_switches",
        "total_off_time_sec",
        "avg_off_time_sec",
        "off_time_variance",
        "switch_rate_per_min",
        "mean_gap_sec",
        "std_gap_sec",
        "cv_gap",
        "long_gap_count",
        "burst_count",
        "total_answers",
        "unique_questions",
        "revisions",
        "revision_ratio",
        "max_revisions_single_q"
    ])
    writer.writerows(metric_rows)

print("Done. Wrote events.csv and metrics.csv")
