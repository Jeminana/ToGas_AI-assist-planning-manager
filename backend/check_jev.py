"""Explicit one-request live smoke check; never reads/writes application data.

Run only when intending to use the shared service. .env stays unchanged.
"""
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
from ai import analyze_result
from jev_api import JEV_ENDPOINT, JevError


def main():
    os.environ['TOGAS_AI_MODE'] = 'jev'  # This process only; .env is not modified.
    report = {
        'created_at': datetime.now(timezone.utc).isoformat(),
        'endpoint': JEV_ENDPOINT, 'max_http_attempts': 1,
        'automatic_retries': False,
        'input': 'Meet my friend tomorrow.', 'reference_date': '2026-11-12',
    }
    try:
        result = analyze_result(report['input'], date.fromisoformat(report['reference_date']))
        report.update(status='connected', result=result)
        exit_code = 0
    except JevError as exc:
        report.update(status='failed', http_status=exc.status, error=str(exc))
        exit_code = 1
    except Exception as exc:
        report.update(status='failed', error=f'Local processing failed ({type(exc).__name__}). No automatic retry was made.')
        exit_code = 1
    output = Path(__file__).parent / 'evaluation' / 'jev-smoke.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
