#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${LMS_URL:-https://lms.dymova-english.ru}"
TOKEN="${LMS_TOKEN:?Set LMS_TOKEN to a valid cabinet Bearer token}"
STUDENT_ID="${LMS_STUDENT_ID:?Set LMS_STUDENT_ID to the active child id}"
AUTH=(-H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json')

catalog=$(curl -fsS "${BASE_URL}/api/lk/learning/catalog" "${AUTH[@]}")
echo "$catalog" | jq -e '.units | length > 0' >/dev/null
session=$(curl -fsS -X POST "${BASE_URL}/api/lk/learning/sessions" "${AUTH[@]}" \
  --data "{\"student_id\":${STUDENT_ID},\"unit_id\":\"pre-a1.school\"}")
session_id=$(echo "$session" | jq -r .session_id)
test -n "$session_id" -a "$session_id" != null

while IFS= read -r challenge; do
  id=$(echo "$challenge" | jq -r .id)
  kind=$(echo "$challenge" | jq -r .kind)
  case "$kind" in
    translate_choice|listen_choice|grammar_choice|read_choice) answer='{"index":0}' ;;
    read_true_false) answer='{"value":true}' ;;
    speak) answer='{"transcript":"I have a brother"}' ;;
    write) answer='{"text":"pen"}' ;;
    *) echo "Unsupported challenge kind: $kind" >&2; exit 1 ;;
  esac
  curl -fsS -X POST "${BASE_URL}/api/lk/learning/sessions/${session_id}/answer" "${AUTH[@]}" \
    --data "{\"student_id\":${STUDENT_ID},\"challenge_id\":\"${id}\",\"answer\":${answer}}" >/dev/null
done < <(echo "$session" | jq -c '.challenges[]')

result=$(curl -fsS -X POST "${BASE_URL}/api/lk/learning/sessions/${session_id}/finish" "${AUTH[@]}" \
  --data "{\"student_id\":${STUDENT_ID}}")
echo "$result" | jq -e '.points >= 0' >/dev/null
progress=$(curl -fsS "${BASE_URL}/api/lk/learning/progress?student_id=${STUDENT_ID}" "${AUTH[@]}")
echo "$progress" | jq -e '.points >= 0 and (.mastery | type == "array")' >/dev/null
echo "LMS AUTH SMOKE: PASS"
