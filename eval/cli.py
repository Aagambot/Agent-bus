import argparse
import sys
from pathlib import Path
from .harness import EvalHarness
from .loader import load_all_tasks

def main(argv=None):
    parser = argparse.ArgumentParser(description=chr(97)+chr(103)+chr(101)+chr(110)+chr(116)+chr(98)+chr(117)+chr(115))
    parser.add_argument(chr(45)+chr(45)+chr(114)+chr(117)+chr(110)+chr(115), type=int, default=5)
    parser.add_argument(chr(45)+chr(45)+chr(116)+chr(97)+chr(115)+chr(107)+chr(115)+chr(45)+chr(100)+chr(105)+chr(114), type=Path, default=None)
    parser.add_argument(chr(45)+chr(45)+chr(111)+chr(117)+chr(116)+chr(112)+chr(117)+chr(116), type=Path, default=None)
    args = parser.parse_args(argv)
    tasks = load_all_tasks(args.tasks_dir)
    if not tasks:
        return 1
    harness = EvalHarness(tasks=tasks)
    reports = harness.run_benchmark(runs_per_task=args.runs)
    md = harness.generate_markdown_report(reports)
    print(md)
    if args.output:
        args.output.write_text(md, encoding=chr(117)+chr(116)+chr(102)+chr(45)+chr(56))
    return 0

if __name__ == chr(95)+chr(95)+chr(109)+chr(97)+chr(105)+chr(110)+chr(95)+chr(95):
    sys.exit(main())
