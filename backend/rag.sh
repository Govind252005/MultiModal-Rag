#!/usr/bin/env bash
# ================================================================
#  Multimodal Offline RAG  --  Interactive Terminal CLI
#  Everything the browser UI does, from your terminal.
#
#  Requirements:  curl  jq
#    Linux/macOS : sudo apt install curl jq
#    Windows WSL : sudo apt install curl jq
#    Git Bash    : curl built-in; get jq -> https://jqlang.github.io/jq/
#
#  Usage:
#    bash rag.sh                       -- local server (default)
#    bash rag.sh --url http://IP:8000  -- remote/LAN server
# ================================================================

BASE="${RAG_URL:-http://localhost:8000}"
TOKEN_FILE="$HOME/.rag_token"
SESSION_FILE="$HOME/.rag_session"
TOKEN=""
SESSION=""
USER_EMAIL=""
TOP_K=5

[[ "${1:-}" == "--url" && -n "${2:-}" ]] && BASE="$2"

R="\033[0;31m" G="\033[0;32m" Y="\033[1;33m"
C="\033[0;36m" B="\033[1m"    D="\033[2m"    X="\033[0m"

ok()   { echo -e "${G}  [OK]${X}  $*"; }
err()  { echo -e "${R}  [ERR]${X} $*"; }
info() { echo -e "${C}  [i]${X}   $*"; }
warn() { echo -e "${Y}  [!!]${X}  $*"; }
hdr()  { echo -e "\n${B}${C}=== $* ===${X}\n"; }
sep()  { echo -e "${D}  ------------------------------------------------${X}"; }

need() { command -v "$1" &>/dev/null || { err "Install $1 first: sudo apt install $1"; exit 1; }; }
need curl; need jq

# ---- token / session helpers ----------------------------------------
load_token()   { [[ -f "$TOKEN_FILE" ]]   && TOKEN=$(cat "$TOKEN_FILE")   || TOKEN=""; }
load_session() { [[ -f "$SESSION_FILE" ]] && SESSION=$(cat "$SESSION_FILE") || SESSION=""; }
save_token()   { printf '%s' "$1" > "$TOKEN_FILE"; chmod 600 "$TOKEN_FILE"; }
save_session() { printf '%s' "$1" > "$SESSION_FILE"; }
clear_auth()   { rm -f "$TOKEN_FILE" "$SESSION_FILE"; TOKEN=""; SESSION=""; }

# ---- HTTP helpers -------------------------------------------------------
api_get()    { curl -sS -H "Authorization: Bearer $TOKEN" "$BASE$1"; }
api_delete() { curl -sS -X DELETE -H "Authorization: Bearer $TOKEN" "$BASE$1"; }
api_post() {
  local url="$1" body="$2"
  curl -sS -X POST \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "$body" "$BASE$url"
}
api_form() {
  local url="$1"; shift
  curl -sS -X POST -H "Authorization: Bearer $TOKEN" "$@" "$BASE$url"
}
check_error() {
  local d; d=$(echo "$1" | jq -r '.detail // empty' 2>/dev/null)
  [[ -n "$d" ]] && { err "$d"; return 1; }
  return 0
}

# ---- banner ---------------------------------------------------------
print_banner() {
  echo ""
  echo "  +--------------------------------------------------+"
  echo "  |    Multimodal Offline RAG  --  Terminal CLI      |"
  echo "  |  Documents . Images . Audio . Ollama LLM         |"
  echo "  +--------------------------------------------------+"
  echo ""
  info "Server: $BASE"
}

# ---- auth -----------------------------------------------------------
do_register() {
  hdr "Create Account"
  read -rp "  Email    : " email
  read -rsp "  Password (min 6 chars): " pw; echo
  read -rsp "  Confirm password      : " pw2; echo
  [[ "$pw" != "$pw2" ]] && { err "Passwords do not match."; return 1; }
  local jval_email jval_pw
  jval_email=$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$email" 2>/dev/null || printf '"%s"' "$email")
  jval_pw=$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$pw" 2>/dev/null || printf '"%s"' "$pw")
  local body; body=$(printf '{"email":%s,"password":%s}' "$jval_email" "$jval_pw")
  local r; r=$(curl -sS -X POST -H "Content-Type: application/json" -d "$body" "$BASE/api/auth/register")
  check_error "$r" || return 1
  TOKEN=$(echo "$r" | jq -r '.token')
  USER_EMAIL=$(echo "$r" | jq -r '.user.email')
  save_token "$TOKEN"
  ok "Account created! Signed in as $USER_EMAIL"
}

do_login() {
  hdr "Sign In"
  read -rp "  Email    : " email
  read -rsp "  Password : " pw; echo
  local jval_email jval_pw
  jval_email=$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$email" 2>/dev/null || printf '"%s"' "$email")
  jval_pw=$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$pw" 2>/dev/null || printf '"%s"' "$pw")
  local body; body=$(printf '{"email":%s,"password":%s}' "$jval_email" "$jval_pw")
  local r; r=$(curl -sS -X POST -H "Content-Type: application/json" -d "$body" "$BASE/api/auth/login")
  check_error "$r" || return 1
  TOKEN=$(echo "$r" | jq -r '.token')
  USER_EMAIL=$(echo "$r" | jq -r '.user.email')
  save_token "$TOKEN"
  ok "Signed in as $USER_EMAIL"
}

verify_token() {
  load_token; [[ -z "$TOKEN" ]] && return 1
  local r; r=$(api_get /api/auth/me 2>/dev/null)
  USER_EMAIL=$(echo "$r" | jq -r '.user.email // empty' 2>/dev/null)
  [[ -n "$USER_EMAIL" ]]
}

auth_flow() {
  hdr "Authentication"
  verify_token && { ok "Already signed in as $USER_EMAIL"; return 0; }
  echo "  1) Sign in   2) Create account   3) Quit"
  read -rp "  Choice [1/2/3]: " ch
  case "$ch" in
    1) do_login    || auth_flow ;;
    2) do_register || auth_flow ;;
    3) exit 0 ;;
    *) warn "Invalid choice."; auth_flow ;;
  esac
}

do_logout() {
  read -rp "  Really log out? [y/N]: " yn
  [[ "$yn" =~ ^[Yy]$ ]] && { clear_auth; ok "Logged out."; exit 0; }
  info "Logout cancelled."
}

# ---- sessions -------------------------------------------------------
list_sessions_cmd() {
  hdr "Your Chats"
  local r; r=$(api_get /api/sessions)
  local cnt; cnt=$(echo "$r" | jq '.sessions|length')
  [[ "$cnt" -eq 0 ]] && { info "No chats yet."; return; }
  echo "$r" | jq -r '.sessions[] | "  \(.id)  \(.title)  [\(.file_count) files, \(.message_count) msgs]"'
}

select_or_create_session() {
  hdr "Select or Create Chat"
  local r; r=$(api_get /api/sessions)
  local cnt; cnt=$(echo "$r" | jq '.sessions|length')
  if [[ "$cnt" -gt 0 ]]; then
    echo "  Existing chats:"
    local i=1
    while IFS= read -r line; do
      echo "  $i) $line"
      ((i++))
    done < <(echo "$r" | jq -r '.sessions[] | .id + "  " + .title + "  [" + (.file_count|tostring) + " files]"')
    echo "  n) New chat"
    read -rp "  Pick number or n: " pick
    if [[ "$pick" =~ ^[0-9]+$ ]]; then
      local idx; idx=$((pick-1))
      SESSION=$(echo "$r" | jq -r --argjson i "$idx" '.sessions[$i].id')
      local t; t=$(echo "$r" | jq -r --argjson i "$idx" '.sessions[$i].title')
      save_session "$SESSION"
      ok "Using: $t  (id: $SESSION)"; return
    fi
  fi
  read -rp "  Chat title [New chat]: " title
  title="${title:-New chat}"
  local jval_title
  jval_title=$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$title" 2>/dev/null || printf '"%s"' "$title")
  local body; body=$(printf '{"title":%s}' "$jval_title")
  local nr; nr=$(api_post /api/sessions "$body")
  SESSION=$(echo "$nr" | jq -r '.id')
  save_session "$SESSION"
  ok "Created: $title  (id: $SESSION)"
}

ensure_session() {
  load_session
  [[ -z "$SESSION" ]] && select_or_create_session
}

delete_session_cmd() {
  ensure_session
  hdr "Delete Current Chat"
  warn "This permanently deletes the chat and all its indexed files."
  read -rp "  Type DELETE to confirm: " c
  [[ "$c" != "DELETE" ]] && { info "Cancelled."; return; }
  api_delete "/api/sessions/$SESSION" > /dev/null
  rm -f "$SESSION_FILE"; SESSION=""
  ok "Chat deleted."
}

# ---- ingest / files -------------------------------------------------
ingest_files() {
  ensure_session
  hdr "Ingest Files into Chat"
  info "Supported: PDF, DOCX, PNG, JPG, MP3, WAV, M4A"
  echo "  Enter file paths one by one. Empty line when done."
  echo ""
  local files=()
  while true; do
    read -rp "  File path: " fpath
    [[ -z "$fpath" ]] && break
    if [[ ! -f "$fpath" ]]; then
      err "Not found: $fpath"
    else
      files+=("$fpath")
      ok "Queued: $(basename "$fpath")"
    fi
  done
  [[ ${#files[@]} -eq 0 ]] && { warn "No files provided."; return; }
  info "Ingesting ${#files[@]} file(s)...  (may take a while)"
  sep
  local form=(-F "session_id=$SESSION")
  for fi in "${files[@]}"; do form+=(-F "files=@$fi"); done
  local res; res=$(api_form /api/ingest "${form[@]}")
  check_error "$res" || return 1
  echo "$res" | jq -r '.ingested[] | if .error then "  [ERR] " + .file + ": " + .error else "  [OK]  " + .file + " -- " + .modality + ", " + (.chunks|tostring) + " chunks" end'
  sep; ok "Done. Files in this chat:"
  echo "$res" | jq -r '.files[] | "  - " + .file + "  (" + .modality + ", " + (.chunks|tostring) + " chunks)"'
}

list_files_cmd() {
  ensure_session
  hdr "Files in Current Chat"
  local res; res=$(api_get "/api/files?session_id=$SESSION")
  local cnt; cnt=$(echo "$res" | jq '.files|length')
  [[ "$cnt" -eq 0 ]] && { info "No files ingested yet."; return; }
  echo "$res" | jq -r '.files[] | "  " + .file + "  (" + .modality + ", " + (.chunks|tostring) + " chunks)"'
}

delete_file_cmd() {
  ensure_session
  hdr "Delete a File"
  list_files_cmd
  echo ""
  read -rp "  Filename to delete (exact name): " fname
  [[ -z "$fname" ]] && return
  api_delete "/api/files/$fname?session_id=$SESSION" > /dev/null
  ok "Deleted: $fname"
}

# ---- queries --------------------------------------------------------
print_answer() {
  local res="$1"
  sep
  echo "  ANSWER:"
  echo "  -------"
  echo "$res" | jq -r '.answer'
  echo ""
  sep
  echo "  CITATIONS:"
  local cnt; cnt=$(echo "$res" | jq '.citations|length')
  if [[ "$cnt" -eq 0 ]]; then info "No citations returned."; return; fi
  echo "$res" | jq -r '.citations[] |
    "  [" + (.index|tostring) + "] " + .file +
    (if .page      then "  page "  + (.page|tostring)  else "" end) +
    (if .timestamp then "  at "    + .timestamp         else "" end) +
    "  [" + .modality + "]" +
    "\n      " + ((.snippet // "")[0:160])'
  local u; u=$(echo "$res" | jq -r '.used_llm')
  [[ "$u" == "true" ]] && ok "Answer generated by LLM" || warn "LLM offline -- top source shown"
}

query_text() {
  ensure_session
  hdr "Ask a Question"
  info "Chat: $SESSION   Top-K: $TOP_K"
  echo ""
  read -rp "  Your question: " q_input
  [[ -z "$q_input" ]] && return
  info "Searching and generating answer..."
  local jval; jval=$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$q_input" 2>/dev/null || printf '"%s"' "$q_input")
  local body; body=$(printf '{"session_id":"%s","query":%s,"top_k":%d,"modality":"all"}' "$SESSION" "$jval" "$TOP_K")
  local res; res=$(api_post /api/query "$body")
  check_error "$res" || return 1
  print_answer "$res"
}

query_image_file() {
  ensure_session
  hdr "Query by Image"
  info "Upload an image to find visually related content in your library."
  read -rp "  Path to image (PNG/JPG/WEBP): " fpath
  [[ ! -f "$fpath" ]] && { err "File not found: $fpath"; return 1; }
  info "Running CLIP visual search..."
  local res; res=$(api_form /api/query/image \
    -F "session_id=$SESSION" -F "top_k=$TOP_K" -F "file=@$fpath")
  check_error "$res" || return 1
  local cap; cap=$(echo "$res" | jq -r '.query_caption // empty')
  local ocr; ocr=$(echo "$res" | jq -r '.query_ocr // empty')
  [[ -n "$cap" ]] && info "Caption detected: $cap"
  [[ -n "$ocr" ]] && info "OCR text in image: $ocr"
  print_answer "$res"
}

query_audio_file() {
  ensure_session
  hdr "Query by Audio"
  info "Audio is transcribed then searched against your library."
  read -rp "  Path to audio (mp3/wav/m4a): " fpath
  [[ ! -f "$fpath" ]] && { err "File not found: $fpath"; return 1; }
  info "Transcribing and searching... (may take a minute)"
  local res; res=$(api_form /api/query/audio \
    -F "session_id=$SESSION" -F "top_k=$TOP_K" -F "file=@$fpath")
  check_error "$res" || return 1
  local tr; tr=$(echo "$res" | jq -r '.transcript // empty')
  local lang; lang=$(echo "$res" | jq -r '.language // "unknown"')
  [[ -n "$tr" ]] && info "Transcribed ($lang): $tr"
  print_answer "$res"
}

transcribe_only() {
  ensure_session
  hdr "Transcribe Audio Only"
  read -rp "  Path to audio file: " fpath
  [[ ! -f "$fpath" ]] && { err "File not found: $fpath"; return 1; }
  info "Transcribing..."
  local res; res=$(api_form /api/transcribe \
    -F "session_id=$SESSION" -F "file=@$fpath")
  check_error "$res" || return 1
  local txt; txt=$(echo "$res" | jq -r '.text')
  local lang; lang=$(echo "$res" | jq -r '.language // "unknown"')
  ok "Language: $lang"; sep; echo "$txt"; sep
}

# ---- smart actions --------------------------------------------------
summarize_doc() {
  ensure_session
  hdr "Summarize Documents"
  read -rp "  Topic [ENTER = all docs]: " q_input
  q_input="${q_input:-Summarize the main points of all documents}"
  local jval; jval=$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$q_input" 2>/dev/null || printf '"%s"' "$q_input")
  local body; body=$(printf '{"session_id":"%s","query":%s,"top_k":%d,"modality":"document"}' "$SESSION" "$jval" "$TOP_K")
  info "Generating summary..."
  local res; res=$(api_post /api/summarize "$body")
  check_error "$res" || return 1
  print_answer "$res"
}

extract_entities() {
  ensure_session
  hdr "Extract Entities / Structured Data"
  info "Examples: extract all names and dates | list all monetary amounts"
  read -rp "  What to extract: " q_input
  [[ -z "$q_input" ]] && return
  local jval; jval=$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$q_input" 2>/dev/null || printf '"%s"' "$q_input")
  local body; body=$(printf '{"session_id":"%s","query":%s,"top_k":%d,"modality":"all"}' "$SESSION" "$jval" "$TOP_K")
  info "Extracting..."
  local res; res=$(api_post /api/extract "$body")
  check_error "$res" || return 1
  print_answer "$res"
}

# ---- source / media -------------------------------------------------
view_source() {
  hdr "View Full Source by Citation ID"
  read -rp "  Enter source ID (from citation): " sid
  [[ -z "$sid" ]] && return
  local res; res=$(api_get "/api/source/$sid")
  check_error "$res" || return 1
  sep
  echo "$res" | jq -r '"  File    : " + .file'
  echo "$res" | jq -r '"  Modality: " + .modality'
  echo "$res" | jq -r '"  Type    : " + .source_type'
  echo "$res" | jq -r 'if .page      then "  Page    : " + (.page|tostring)                                   else "" end'
  echo "$res" | jq -r 'if .timestamp then "  Time    : " + .timestamp                                         else "" end'
  echo "$res" | jq -r 'if .chunk     then "  Chunk   : " + (.chunk|tostring) + " of " + (.chunk_total|tostring) else "" end'
  sep; echo "  Full text:"
  echo "$res" | jq -r '.full_text'
  sep
}

download_media() {
  ensure_session
  hdr "Download an Ingested Media File"
  list_files_cmd; echo ""
  read -rp "  Filename to download: " fname
  [[ -z "$fname" ]] && return
  info "Downloading $fname..."
  curl -sSL -H "Authorization: Bearer $TOKEN" "$BASE/api/media/$SESSION/$fname" -o "$fname"
  ok "Saved as: $fname"
}

# ---- system ---------------------------------------------------------
health_check() {
  hdr "System Health"
  local res; res=$(curl -sS "$BASE/api/health")
  echo "$res" | jq -r '"  Status    : " + .status'
  echo "$res" | jq -r '"  Device    : " + .device'
  echo "$res" | jq -r '"  LLM Model : " + .llm_model'
  echo "$res" | jq -r '"  OCR Engine: " + .ocr_engine'
  echo "$res" | jq -r '"  LLM Ready : " + (.llm_available|tostring)'
  echo "$res" | jq -r '"  Text chunks: " + (.index.text_items|tostring)'
  echo "$res" | jq -r '"  Img  chunks: " + (.index.image_items|tostring)'
}

change_settings() {
  hdr "Settings"
  echo "  Current Top-K: $TOP_K"
  echo "  Top-K = number of source chunks retrieved per query."
  echo "  3 = fast   5 = balanced (default)   10 = thorough"
  read -rp "  New Top-K value [1-20]: " val
  if [[ "$val" =~ ^[0-9]+$ && "$val" -ge 1 && "$val" -le 20 ]]; then
    TOP_K="$val"
    ok "Top-K set to $TOP_K"
  else
    warn "Invalid value. Keeping current $TOP_K."
  fi
}

reset_all() {
  hdr "RESET -- Delete ALL Your Data"
  warn "This permanently deletes ALL your chats, files, and indexed data."
  read -rp "  Type RESET ALL to confirm: " confirm
  [[ "$confirm" != "RESET ALL" ]] && { info "Cancelled."; return; }
  local res; res=$(curl -sS -X POST -H "Authorization: Bearer $TOKEN" "$BASE/api/reset")
  rm -f "$SESSION_FILE"; SESSION=""
  ok "All data deleted."
}

# ---- main menu ------------------------------------------------------
main_menu() {
  while true; do
    echo ""; sep
    echo "  Chat   : ${SESSION:-<none selected>}"
    echo "  User   : $USER_EMAIL   Server: $BASE"
    sep
    echo "  1) Switch/create chat    2) List all chats"
    echo "  3) Ingest files          4) List files in chat     5) Delete file"
    echo "  6) Ask a question        7) Query by image         8) Query by audio"
    echo "  9) Summarize docs       10) Extract entities      11) Transcribe audio"
    echo " 12) View source by ID    13) Download ingested file"
    echo " 14) Health check         15) Settings (Top-K: $TOP_K)"
    echo " 16) Delete current chat  17) RESET all data        18) Log out"
    echo "  0) Quit"
    echo ""
    read -rp "  Choice: " ch
    case "$ch" in
      1)  select_or_create_session ;;
      2)  list_sessions_cmd ;;
      3)  ingest_files ;;
      4)  list_files_cmd ;;
      5)  delete_file_cmd ;;
      6)  query_text ;;
      7)  query_image_file ;;
      8)  query_audio_file ;;
      9)  summarize_doc ;;
      10) extract_entities ;;
      11) transcribe_only ;;
      12) view_source ;;
      13) download_media ;;
      14) health_check ;;
      15) change_settings ;;
      16) delete_session_cmd ;;
      17) reset_all ;;
      18) do_logout ;;
      0)  echo ""; echo "  Bye!"; echo ""; exit 0 ;;
      *)  warn "Unknown option." ;;
    esac
  done
}

# ---- entry point ----------------------------------------------------
print_banner
auth_flow
load_session
if [[ -n "$SESSION" ]]; then
  stitle=$(api_get "/api/sessions/$SESSION" 2>/dev/null | jq -r '.title // empty' 2>/dev/null)
  [[ -n "$stitle" ]] && ok "Resuming chat: $stitle  (id: $SESSION)"
else
  select_or_create_session
fi
main_menu
