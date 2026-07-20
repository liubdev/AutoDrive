"""
Demo: Launch notepad, type text, save file

Run:
    python main.py script scripts/demo_notepad.py
"""

import time
import sys
from pathlib import Path

# Fallback when running standalone (not via main.py script cmd)
try:
    auto
except NameError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from agent import AutoController

    auto = AutoController()
    _standalone = True
else:
    _standalone = False

# 1. Launch notepad
auto.launch("notepad.exe")
time.sleep(1)

# 2. Type some text
auto.send_keys("Hello from AutoCar!")
time.sleep(0.5)

# 3. Click menu by auto_id
auto.click("File", by="auto_id")
time.sleep(0.3)

# 4. Click Save As by text
auto.click("Save As...", by="text")
time.sleep(1)

# 5. Type filename
auto.type_text("", "autocar_demo.txt", by="text", timeout=3)
time.sleep(0.3)

# 6. Click Save button
auto.click("Save", by="name")
time.sleep(1)

# 7. Report
report = auto.report()
print(
    f"\nDone: {report['steps_total']} steps, "
    f"{report['success']} OK, {report['failures']} FAIL"
)

# Close if standalone
if _standalone:
    auto.close()
