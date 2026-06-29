#!/usr/bin/env bash
# End-to-end demo / evidence capture for Provenance Guard.
# Usage: start the server in one terminal (python app.py), then run:  bash demo.sh
set -u
BASE="${BASE:-http://127.0.0.1:5000}"

hr(){ printf '\n========== %s ==========\n' "$1"; }
post(){ curl -s --noproxy '*' -X POST "$BASE/submit" -H "Content-Type: application/json" -d "$1"; }

# 0) server reachable?
if ! curl -s --noproxy '*' -f "$BASE/health" >/dev/null; then
  echo "Server not reachable at $BASE — start it first:  python app.py"; exit 1
fi

hr "1) CALIBRATION CHECK (selftest.py)"
python selftest.py

hr "2) CLEARLY-AI SUBMISSION  (expect: likely_ai)"
post '{"text":"Artificial intelligence represents a transformative paradigm shift in modern society. It is important to note that while the benefits are numerous, it is equally essential to consider the ethical implications. Furthermore, stakeholders across various sectors must collaborate to ensure responsible deployment of these powerful systems.","creator_id":"demo-ai"}' | python -m json.tool

hr "3) CLEARLY-HUMAN SUBMISSION  (expect: likely_human)"
HUMAN=$(post '{"text":"ok so i finally tried that new ramen place downtown and honestly? underwhelming. the broth was fine but they put WAY too much sodium in it and i was thirsty for like three hours after. my friend got the spicy version and said it was better. probably wont go back unless someone drags me there","creator_id":"demo-human"}')
echo "$HUMAN" | python -m json.tool
CID=$(echo "$HUMAN" | python -c "import sys,json;print(json.load(sys.stdin)['content_id'])")
echo "captured content_id: $CID"

hr "4) APPEAL the human submission  (expect: status under_review)"
curl -s --noproxy '*' -X POST "$BASE/appeal" -H "Content-Type: application/json" \
  -d "{\"content_id\":\"$CID\",\"creator_reasoning\":\"I wrote this myself from personal experience. I am a non-native English speaker and my writing may appear more formal than typical.\"}" | python -m json.tool

hr "5) AUDIT LOG  (expect: >=3 entries, one under_review with appeal_reasoning)"
curl -s --noproxy '*' "$BASE/log" | python -m json.tool

hr "6) RATE LIMIT  (expect: 200 x10 then 429)"
for i in $(seq 1 12); do
  curl -s --noproxy '*' -o /dev/null -w "%{http_code}\n" -X POST "$BASE/submit" \
    -H "Content-Type: application/json" \
    -d '{"text":"This is a test submission for rate limit testing purposes only.","creator_id":"ratelimit-test"}'
done

echo; echo "Done. Copy this output back to share the real-score evidence."
