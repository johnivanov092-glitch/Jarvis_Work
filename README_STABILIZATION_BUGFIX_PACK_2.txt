JARVIS STABILIZATION BUGFIX PACK 2

Что внутри:
- frontend/src/api/ide.js
- frontend/src/components/StabilizationPreflightPanel.jsx
- frontend/src/components/CodeWorkspace.jsx
- README_STABILIZATION_BUGFIX_PACK_2.txt

Что делает:
- встраивает Preflight прямо в CodeWorkspace
- прогоняет preflight перед batch apply
- прогоняет preflight перед batch verify
- блокирует apply/verify при fail checks
- подключает Preflight к:
  - Phase19
  - Phase20
  - Phase21

Это уже рабочий stabilization шаг для защиты execution flow.
