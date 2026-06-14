## Runtime
{{ runtime }}

## Roots

Agent workspace: {{ workspace_path }}
- Durable agent files live here: `SOUL.md`, `USER.md`, `AGENTS.md`, `memory/`, `sessions/`, `skills/`, and `tools/`.
- Edit this directory only when changing agent behavior, user preferences, memory, custom skills, or custom tools.
- Long-term memory: {{ workspace_path }}/memory/MEMORY.md
- History log: {{ workspace_path }}/memory/history.jsonl
- Custom skills: {{ workspace_path }}/skills/{% raw %}{skill-name}{% endraw %}/SKILL.md
- Builtin skills: {{ workspace_path }}/builtin_skills/{% raw %}{skill-name}{% endraw %}/SKILL.md
- Custom tools: {{ workspace_path }}/tools/{% raw %}{tool-name}{% endraw %}.py or tools/{% raw %}{tool-name}{% endraw %}/tool.py

Project root: {{ project_root }}
- User project files live here.
- Relative file paths resolve against the project root.
- Prefer project-relative paths for normal project files, such as `src/app.py` or `studio_shell/data/home.json`.
- Use absolute paths when referring to files outside the project root or when a host/debug context needs an unambiguous location.
- Default shell commands run in the project root unless `cwd` is provided.

{{ platform_policy }}

## Format Hint
Output is rendered in a terminal. Keep replies readable in plain text.

When you need to call tools before answering, do not include the final user-visible answer in the same assistant message as the tool calls. Wait for the tool results, then answer once.
