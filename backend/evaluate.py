"""Small labeled evaluation. Mock results are pipeline checks, NOT Jev quality."""
import argparse
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
from ai import analyze, ai_mode
from jev_api import JevError


def evaluate(examples, reference):
    rows = []
    for example in examples:
        try:
            proposals = analyze(example['text'], reference)
            prediction = proposals[0] if proposals else None
            rows.append({'expected': example, 'predicted': prediction, 'error': None})
        except Exception as exc:
            rows.append({'expected': example, 'predicted': None, 'error': type(exc).__name__})
            if ai_mode() == 'jev' and isinstance(exc, JevError):
                break  # Do not spend shared calls after a service/configuration failure.
    positives = [row for row in rows if row['expected']['actionable']]
    tp = sum(bool(row['predicted']) and row['expected']['actionable'] for row in rows)
    fp = sum(bool(row['predicted']) and not row['expected']['actionable'] for row in rows)
    return {
        'examples': len(rows), 'errors': sum(row['error'] is not None for row in rows),
        'actionability_accuracy': sum(not row['error'] and bool(row['predicted']) == row['expected']['actionable'] for row in rows) / len(rows),
        'actionability_precision': tp / (tp + fp) if tp + fp else 0,
        'actionability_recall': tp / len(positives) if positives else 0,
        'category_accuracy_on_actionable_examples': sum(bool(row['predicted']) and row['predicted']['category'] == row['expected']['category'] for row in positives) / len(positives) if positives else 0,
        'deadline_accuracy_on_actionable_examples': sum(bool(row['predicted']) and row['predicted']['due_date'] == row['expected'].get('due_date') for row in positives) / len(positives) if positives else 0,
    }, rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['mock', 'local', 'jev'], default='mock')
    parser.add_argument('--limit', type=int, help='Maximum number of examples; required for live Jev evaluation')
    parser.add_argument('--reference-date', type=date.fromisoformat, default=date(2026, 11, 12))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    os.environ['TOGAS_AI_MODE'] = args.mode
    base = Path(__file__).parent / 'evaluation'
    examples = json.loads((base / 'examples.json').read_text(encoding='utf-8'))
    if args.mode == 'jev' and args.limit is None:
        parser.error('Live evaluation requires an explicit --limit to cap shared API calls.')
    if args.limit is not None:
        if not 1 <= args.limit <= len(examples):
            parser.error(f'--limit must be between 1 and {len(examples)}')
        examples = examples[:args.limit]
    metrics, rows = evaluate(examples, args.reference_date)
    output = args.output or base / f'{args.mode}-results.json'
    report = {'mode': args.mode, 'is_jev_evaluation': args.mode in {'local', 'jev'}, 'requested_examples': len(examples), 'reference_date': args.reference_date.isoformat(), 'created_at': datetime.now(timezone.utc).isoformat(), 'metrics': metrics, 'results': rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({'mode': args.mode, 'metrics': metrics, 'output': str(output)}, indent=2))
