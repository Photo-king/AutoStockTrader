#!/usr/bin/env python3
"""Run a read-only PowerShell probe through StockAgent's pinned SSH connection."""
import base64
import pathlib
import subprocess

helper = pathlib.Path('/Users/photo-king/Projects/StockAgent/scripts/windows-ssh.sh')
script = pathlib.Path(__file__).parents[1] / 'windows' / 'inspect.ps1'
encoded = base64.b64encode(script.read_text().encode('utf-16le')).decode('ascii')
raise SystemExit(subprocess.call([str(helper), '-o', 'BatchMode=yes',
    'powershell -NoProfile -NonInteractive -EncodedCommand ' + encoded]))
