from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
required = [
    'app.py','install.sh','requirements.txt','VERSION.json','BUILD_INFO.json',
    'templates/networking.html','static/rc001.js','static/rc001.css'
]
missing=[name for name in required if not (ROOT/name).is_file()]
if missing:
    raise SystemExit('Missing required files: '+', '.join(missing))
subprocess.run([sys.executable,'-m','compileall','-q',str(ROOT)],check=True)
js=(ROOT/'static/rc001.js').read_text()
html=(ROOT/'templates/networking.html').read_text()
environment_html=(ROOT/'templates/environment.html').read_text()
base_html=(ROOT/'templates/base.html').read_text()
home_html=(ROOT/'templates/home.html').read_text()
css=(ROOT/'static/rc001.css').read_text()
checks={
 'drawer markup':'networkingDeviceDrawer' in html,
 'drawer controller':'networkingOpenDeviceDrawer' in js,
 'status animation':'networkingAnimateStatusChanges' in js,
 'reduced motion':'prefers-reduced-motion' in css,
 'installer target':'/opt/rc001' in (ROOT/'install.sh').read_text(),
 'request import':'render_template, request' in (ROOT/'app.py').read_text(),
 'collapsible networking sections':html.count('networking-collapsible') >= 4,
 'network health precedes topology':html.index('networking-health-section') < html.index('networkingTopology'),
 'weather radar markup':'weatherRadarFrame' in environment_html and 'weather_radar_url' in environment_html,
 'weather radar lazy loading':'loading="lazy"' in environment_html,
 'weather radar controller':'initializeWeatherRadar' in js,
 'weather radar responsive styling':'.weather-radar-shell' in css and '@media (max-width: 680px)' in css,
 'home operations identity':'Home Operations Center' in base_html,
 'dynamic home camera metric':'homeSecurityCameraCount' in home_html and '5 Cameras' not in home_html,
 'dynamic camera controller':'configured_count' in js and 'homeSecurityCameraCount' in js,
}
failed=[name for name,ok in checks.items() if not ok]
if failed:
    raise SystemExit('Validation failed: '+', '.join(failed))
print(json.dumps({'ok':True,'checks':checks},indent=2))
