"""Day 2 mixed-journal checks. Default is offline; live mode needs an explicit cap."""
import argparse
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
from ai import analyze_result
from jev_api import JevError


def evaluate_journals(cases):
    rows = []
    for case in cases:
        try:
            result = analyze_result(case['text'], date.fromisoformat(case['reference_date']))
            remaining = list(result['proposals'])
            checks = []
            for expected in case['expected']:
                span = expected.get('action_span', expected['source_text'])
                actual = next((proposal for proposal in remaining if proposal.get('action_span', proposal['source_text']) == span), None)
                if actual is not None:
                    remaining.remove(actual)
                checks.append({
                    'source_text': expected['source_text'],
                    'actionability_matches': bool(actual) == expected['actionable'],
                    'category_matches': (bool(actual) and actual['category'] == expected['category']) if expected['actionable'] else None,
                    'deadline_matches': (bool(actual) and actual['due_date'] == expected['due_date']) if expected['actionable'] else None,
                })
            rows.append({'id': case['id'], 'result': result, 'checks': checks, 'error': None})
        except Exception as exc:
            message = str(exc) if isinstance(exc, JevError) else f'Local processing failed ({type(exc).__name__}).'
            rows.append({'id': case['id'], 'result': None, 'checks': [], 'error': message})
            break  # Never spend more shared calls after an error.
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['mock', 'jev'], default='mock')
    parser.add_argument('--max-requests', type=int, help='Required in live mode; 1 for English only, 2 for both journals')
    args = parser.parse_args()
    base = Path(__file__).parent / 'evaluation'
    cases = json.loads((base / 'day2-journals.json').read_text(encoding='utf-8'))
    if args.mode == 'jev':
        if args.max_requests is None or not 1 <= args.max_requests <= len(cases):
            parser.error('Live checks require --max-requests 1 or --max-requests 2.')
        cases = cases[:args.max_requests]
    os.environ['TOGAS_AI_MODE'] = args.mode
    rows = evaluate_journals(cases)
    report = {
        'mode': args.mode, 'is_jev_evaluation': args.mode == 'jev',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'live_request_limit': len(cases) if args.mode == 'jev' else 0,
        'automatic_retries': False, 'requested_cases': len(cases), 'results': rows,
    }
    output = base / f'day2-{args.mode}-results.json'
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({'mode': args.mode, 'live_request_limit': report['live_request_limit'], 'cases_processed': len(rows), 'errors': sum(row['error'] is not None for row in rows), 'report': str(output)}, indent=2))
    raise SystemExit(1 if any(row['error'] for row in rows) else 0)
