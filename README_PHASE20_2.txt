JARVIS PHASE 20.2 PATCH

Что внутри:
- frontend/src/components/Phase20Panel.jsx
- frontend/src/components/CodeWorkspace.jsx
- README_PHASE20_2.txt

Что добавляет:
- кнопку Preview Execution в Phase20Panel
- привязку Phase20 к preview/edit loop
- Phase20 теперь умеет:
  Stage -> Preview -> Apply -> Verify

Что делает:
- берёт preview_targets из execution
- открывает первый подходящий файл
- вызывает previewPatch для execution-цели
- сохраняет proposed content в stagedContents
- готовит multi-file execution flow к полуавтоматической работе

Важно:
- backend уже должен содержать endpoints Phase20 и previewPatch
- preview пока запускается по одной execution-цели за раз
- до целиком автономного v1 обычно остаётся 3–4 крупных фазы:
  20.3, 20.4, 21 и стабилизация/cleanup
