{% if system == 'Windows' %}
## Platform Policy (Windows)
- You are running on Windows ({{ shell_name }}). Do not assume GNU tools like `grep`, `sed`, or `awk` exist.
- Windows shell does not support heredoc. Do not use `python - <<'PY'`, `python - <<"PY"`, or any `<<` multi-line shell syntax.
- For multi-line Python, use `write_file` to create a `.py` script, then `exec uv run python <script.py>`.
- If terminal output is garbled, retry with UTF-8 output enabled.
{% else %}
## Platform Policy (POSIX)
- You are running on a POSIX system ({{ shell_name }}).
- For repeatable multi-line Python, prefer `write_file` plus `exec uv run python <script.py>`.
- Use file tools when they are simpler or more reliable than shell commands.
{% endif %}
