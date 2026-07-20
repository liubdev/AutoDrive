# AutoDrive

Windows EXE automation framework — **control-driven** (UIA) + **AI** + **vision**.

## Quick start

```bash
pip install -r requirements.txt
```

## CLI Usage

```
python main.py explore              List all desktop windows
python main.py explore "Chrome"     Probe a running app's controls
python main.py inspect notepad.exe  Launch app and inspect its controls
python main.py goal "type Hello"    AI-driven natural language execution
python main.py run app.exe steps.json  Execute JSON step script
python main.py script demo.py       Execute Python script
python main.py record app.exe 10    Record window state snapshots
```

## Code usage

```python
from agent import AutoController

with AutoController() as ctrl:
    ctrl.launch("notepad.exe")
    ctrl.click("Edit", by="auto_id")    # use auto_id
    ctrl.click("Bold(Ctrl+B)", by="text")  # use text
    ctrl.type_text("", "Hello", by="auto_id")
```

## Architecture

```
config/     Global settings
automation/ Driver, Locator, Actions (core UIA control layer)
inspector/  UI control tree explorer
vision/     Screenshot + OCR (Tesseract)
ai/         LLM client (OpenAI) + prompt templates
agent/      Controller, State, Workflow engine
main.py     CLI entry point
```
