# Build on each target OS: python -m PyInstaller --noconfirm FocusStack.spec
import sys
import runpy
from pathlib import Path

formats = runpy.run_path(str(Path(SPECPATH) / 'src/focus_stacker/core/io/formats.py'))

a = Analysis(['desktop_entry.py'], pathex=['src'], binaries=[], datas=[(str(Path(SPECPATH) / "assets/theme.qss"), "assets")],
             hiddenimports=['rawpy', 'scipy.ndimage'], hookspath=[], runtime_hooks=[],
             excludes=['PyQt5', 'PyQt6', 'tkinter'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='FocusStack',
          debug=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='FocusStack')
if sys.platform == 'darwin':
    app = BUNDLE(coll, name='FocusStack.app', bundle_identifier='local.focusstack.desktop',
                 info_plist={'CFBundleShortVersionString': '3.0.0',
                             'NSHighResolutionCapable': True,
                             'CFBundleDocumentTypes': [{'CFBundleTypeName': 'Stack images',
                                  'CFBundleTypeRole': 'Editor',
                                  'CFBundleTypeExtensions': sorted(ext[1:] for ext in formats['FORMATS']),
                                  'LSHandlerRank': 'Alternate',
                                  'LSItemContentTypes': ['public.tiff', 'public.jpeg', 'public.png',
                                                         'public.camera-raw-image']} ]})
