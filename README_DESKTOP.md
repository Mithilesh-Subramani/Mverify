# Mverify desktop setup

Mverify uses a native Tkinter desktop application. It does not start a browser or web server.

1. Use Python 3.11 or newer.
2. Confirm Tkinter is installed: `python -m tkinter`.
3. Create and activate a virtual environment.
4. Install with `python -m pip install -e '.[dev]'`.
5. Run `python desktop_app.py` or `bash run_mverify.sh`.

The desktop has a project explorer, source preview, analysis summary, topology evidence, specification review, verification planning, UVM scaffold generation and an optional Mcore connection.

All RTL and specification files are read locally. Scan history is stored under `~/.mverify` unless `MVERIFY_HOME` is set.
