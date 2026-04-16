import csv

INPUT_FILE = "metrics.csv"
OUTPUT_FILE = "off-task.txt"


def load_metrics():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def write_report(rows):
    rows.sort(key=lambda r: int(r["student_id"]))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("OFF-TASK TIME REPORT\n")
        f.write("=" * 60 + "\n\n")

        f.write(
            f"{'Student':<10}"
            f"{'Test Time (sec)':<18}"
            f"{'Off-task (sec)':<18}"
            f"{'Off-task %':<12}\n"
        )
        f.write("-" * 60 + "\n")

        for r in rows:
            sid = r["student_id"]

            off_time = float(r.get("total_off_time_sec", 0))

            # prefer explicit duration if present, fallback to last timestamp metric if needed
            test_time = float(r.get("total_test_time_sec", 0) or 0)

            # safeguard (avoid divide-by-zero)
            off_pct = (off_time / test_time * 100) if test_time > 0 else 0.0

            f.write(
                f"{sid:<10}"
                f"{test_time:<18.1f}"
                f"{off_time:<18.1f}"
                f"{off_pct:<12.2f}\n"
            )

        f.write("\nCSV FORMAT\n")
        f.write("student_id,total_test_time_sec,total_off_time_sec,off_task_percent\n")

        for r in rows:
            sid = r["student_id"]
            off_time = float(r.get("total_off_time_sec", 0))
            test_time = float(r.get("total_test_time_sec", 0) or 0)

            off_pct = (off_time / test_time * 100) if test_time > 0 else 0.0

            f.write(f"{sid},{test_time:.1f},{off_time:.1f},{off_pct:.2f}\n")


def main():
    rows = load_metrics()
    write_report(rows)
    print(f"Done. Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
    