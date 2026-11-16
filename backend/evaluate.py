"""Small labeled evaluation. Mock results are pipeline checks, NOT Jev quality."""
import argparse
from datetime import date, datetime, timezone
import json
import os
from collections import Counter
from time import perf_counter
from pathlib import Path
from ai import analyze, ai_mode
from ai import analyze_result
from segmentation import segment
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
            if ai_mode() == 'jev':
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


def normalized_span(text):
    return ' '.join(text.casefold().split()).strip(' .!?。！')


def evaluate_extraction(examples, reference):
    """One-to-one exact action-span scoring, including repeated intentions.

    Segmentation misses and classification misses are separate diagnostics.
    They are not mutually exclusive counts of all errors. No fuzzy matching or
    first-proposal shortcut can hide merged or extra actions.
    """
    rows = []
    tp = fp = fn = exact = category_ok = category_total = dates_ok = dates_total = 0
    segmentation_misses = classification_misses = negative_fp = negative_total = 0
    for example in examples:
        started = perf_counter()
        expected = example['expected_actions']
        ref = date.fromisoformat(example.get('reference_date', reference.isoformat()))
        available = segment(example['text'])
        try:
            result = analyze_result(example['text'], ref)
            proposals, error = result['proposals'], None
        except Exception as exc:
            result, proposals = None, []
            error = str(exc) if isinstance(exc, JevError) else type(exc).__name__
        predicted = [normalized_span(row.get('action_span', row['title'])) for row in proposals]
        expected_spans = [normalized_span(row['action_span']) for row in expected]
        matches = Counter(predicted) & Counter(expected_spans)
        matched = sum(matches.values())
        tp += matched; fp += len(proposals) - matched; fn += len(expected) - matched
        exact += int(not error and len(proposals) == example['expected_count'])
        candidates = Counter(normalized_span(text) for text in available)
        segmentation_misses += sum((Counter(expected_spans) - candidates).values())
        classification_misses += sum(((Counter(expected_spans) & candidates) - Counter(predicted)).values())
        unused = list(range(len(proposals)))
        checks = []
        for target in expected:
            index = next((i for i in unused if normalized_span(target['action_span']) == predicted[i]), None)
            actual = proposals[index] if index is not None else None
            if index is not None:
                unused.remove(index)
            category_match = bool(actual and actual['category'] == target['category']) if target.get('category') else None
            date_match = bool(actual and actual.get('due_date') == target['due_date']) if target.get('due_date') else None
            if category_match is not None:
                category_total += 1; category_ok += int(category_match)
            if date_match is not None:
                dates_total += 1; dates_ok += int(date_match)
            checks.append({'action_span': target['action_span'], 'detected': actual is not None, 'category_matches': category_match, 'explicit_date_matches': date_match,
                           'review_matches': bool(actual and actual['needs_review']) if example['manual_review_required'] else None})
        if example.get('negative_kind') in {'reflection', 'completed'}:
            negative_total += 1; negative_fp += len(proposals)
        rows.append({'id': example['id'], 'expected': example, 'segments': available, 'result': result, 'checks': checks, 'error': error,
                     'evaluation_latency_ms': round((perf_counter() - started) * 1000, 3)})
        if error and ai_mode() == 'jev':
            break  # No more shared calls after any live-mode failure.
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    return {'examples': len(rows), 'errors': sum(row['error'] is not None for row in rows), 'true_positives': tp, 'false_positives': fp, 'false_negatives': fn,
            'task_precision': precision, 'task_recall': recall, 'extraction_f1': 2 * precision * recall / (precision + recall) if precision + recall else 0,
            'exact_task_count_accuracy': exact / len(rows) if rows else 0,
            'category_accuracy': category_ok / category_total if category_total else None, 'category_examples': category_total,
            'explicit_date_accuracy': dates_ok / dates_total if dates_total else None, 'explicit_date_examples': dates_total,
            'reflection_completed_false_positives': negative_fp, 'reflection_completed_examples': negative_total,
            'segmentation_missing_action_spans': segmentation_misses, 'classification_missing_action_spans': classification_misses}, rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['mock', 'local', 'jev'], default='mock')
    parser.add_argument('--limit', type=int, help='Maximum number of examples; required for live Jev evaluation')
    parser.add_argument('--reference-date', type=date.fromisoformat, default=date(2026, 11, 12))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--dataset', type=Path, help='Optional multi-task journal dataset; legacy examples remain the default')
    parser.add_argument('--ids', help='Optional comma-separated journal ids, preserving dataset order')
    args = parser.parse_args()
    os.environ['TOGAS_AI_MODE'] = args.mode
    base = Path(__file__).parent / 'evaluation'
    examples = json.loads((args.dataset or base / 'examples.json').read_text(encoding='utf-8'))
    if args.ids:
        wanted = set(args.ids.split(','))
        if not wanted <= {row.get('id') for row in examples}:
            parser.error('--ids must name entries in the selected dataset')
        examples = [row for row in examples if row.get('id') in wanted]
    if args.mode == 'jev' and args.limit is None:
        parser.error('Live evaluation requires an explicit --limit to cap shared API calls.')
    if args.limit is not None:
        if not 1 <= args.limit <= len(examples):
            parser.error(f'--limit must be between 1 and {len(examples)}')
        examples = examples[:args.limit]
    multi = bool(examples and 'expected_actions' in examples[0])
    metrics, rows = (evaluate_extraction if multi else evaluate)(examples, args.reference_date)
    output = args.output or base / (f'day4-{args.mode}-results.json' if multi else f'{args.mode}-results.json')
    report = {'mode': args.mode, 'is_jev_evaluation': args.mode == 'jev', 'is_local_model_evaluation': args.mode == 'local', 'requested_examples': len(examples), 'live_request_limit': len(examples) if args.mode == 'jev' else 0, 'reference_date': args.reference_date.isoformat(), 'created_at': datetime.now(timezone.utc).isoformat(), 'metrics': metrics, 'results': rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({'mode': args.mode, 'metrics': metrics, 'output': str(output)}, indent=2))
    raise SystemExit(1 if metrics['errors'] else 0)
