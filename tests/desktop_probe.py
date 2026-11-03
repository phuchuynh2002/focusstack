"""Run desktop integration checks in a PyInstaller bundle on macOS."""
import sys
if '--worker' in sys.argv:
    sys.argv.remove('--worker')
    from focus_stacker.cli import main
    raise SystemExit(main())

import json
import tempfile
import traceback
from pathlib import Path
from test_desktop_ui import test_worker_result_and_cancel, test_raw_prompt_and_fileopen_batch, test_add_more_and_stack_selected, test_folder_import_and_preview_does_not_change_checks, test_raw_folder_stack_auto_and_manual, test_settings_roundtrip, test_notebook_loader_controls_and_preview, test_select_none_and_progressive_controls, test_import_prealignment_cache_and_reveal, test_auto_stack_after_import
from focus_stacker.main import Application
app=Application([])
result={}
for check in (test_worker_result_and_cancel,test_raw_prompt_and_fileopen_batch,test_add_more_and_stack_selected,test_folder_import_and_preview_does_not_change_checks,test_raw_folder_stack_auto_and_manual,test_settings_roundtrip,test_notebook_loader_controls_and_preview,test_select_none_and_progressive_controls,test_import_prealignment_cache_and_reveal,test_auto_stack_after_import):
    try:
        with tempfile.TemporaryDirectory(prefix='focusstack-ui-check-') as tmp: check(Path(tmp))
        result[check.__name__]='PASS'
    except Exception:
        result[check.__name__]=traceback.format_exc()
Path('/tmp/focusstack-ui-check-results.json').write_text(json.dumps(result,indent=2))
raise SystemExit(0 if all(v=='PASS' for v in result.values()) else 1)
