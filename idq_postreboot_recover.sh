#!/usr/bin/env bash
set -euo pipefail

# -------------------------
# CONFIG (adjust if needed)
# -------------------------
INFA_HOME="/opt/data/Informatica/IDQ105"
TOMCAT_BIN="${INFA_HOME}/tomcat/bin"
INFA_SERVICE="${TOMCAT_BIN}/infaservice.sh"

TOMCAT_WORK="${INFA_HOME}/tomcat/work"
TOMCAT_TEMP="${INFA_HOME}/tomcat/temp"

ISP_WEBAPPS="${INFA_HOME}/isp/webapps"
ADMINCONSOLE_WEBAPPS="${INFA_HOME}/services/AdministratorConsole/webapps"
SERVICES_DIR="${INFA_HOME}/services"

LOGS_DIR="${INFA_HOME}/logs"
NODE_NAME="node01"        # change if needed

SLEEP_AFTER_REBOOT=60     # give OS/network some time
SHUTDOWN_WAIT_SECS=300    # wait ~5 mins

# Match ONLY IDQ java processes for this INFA_HOME (based on your ps output)
JAVA_MATCH="java.*-DINFA_HOME=${INFA_HOME}"

# Log file inside INFA_HOME
RUNLOG="${LOGS_DIR}/idq_postreboot_recover.log"

# Lock to prevent double runs
LOCKFILE="/tmp/idq_postreboot_recover.lock"

# -------------------------
# FUNCTIONS
# -------------------------
log() { echo "[$(date '+%F %T')] $*" | tee -a "$RUNLOG"; }
die() { log "ERROR: $*"; exit 1; }

require_path_sane() {
  local p="$1"
  [[ -n "$p" ]] || die "Empty path"
  [[ "$p" == /opt/data/Informatica/* ]] || die "Refusing to operate outside /opt/data/Informatica: $p"
  [[ -d "$p" ]] || log "WARN: Directory not found (skipping): $p"
}

safe_rm_dir() {
  local target="$1"
  require_path_sane "$(dirname "$target")"
  if [[ -e "$target" ]]; then
    log "Removing: $target"
    rm -rf --one-file-system "$target"
  else
    log "Skip (not found): $target"
  fi
}

wait_for_java_exit() {
  local deadline=$((SECONDS + SHUTDOWN_WAIT_SECS))
  while (( SECONDS < deadline )); do
    if ! pgrep -f "$JAVA_MATCH" >/dev/null 2>&1; then
      log "No IDQ java processes found."
      return 0
    fi
    log "Waiting for IDQ java processes to exit..."
    sleep 10
  done
  return 1
}

kill_leftover_java() {
  log "Checking for leftover IDQ java processes matching: $JAVA_MATCH"
  local pids
  pids="$(pgrep -f "$JAVA_MATCH" || true)"
  if [[ -z "${pids}" ]]; then
    log "No leftover IDQ java processes to kill."
    return 0
  fi

  log "Leftover IDQ java PIDs: ${pids}"
  log "Sending SIGTERM..."
  kill ${pids} || true
  sleep 15

  pids="$(pgrep -f "$JAVA_MATCH" || true)"
  if [[ -n "${pids}" ]]; then
    log "Still running, sending SIGKILL..."
    kill -9 ${pids} || true
  fi
}

# -------------------------
# MAIN
# -------------------------
umask 022
mkdir -p "$LOGS_DIR" || true
touch "$RUNLOG" || { echo "Cannot write to $RUNLOG"; exit 1; }

exec 200>"$LOCKFILE"
flock -n 200 || { log "Another instance is running; exiting."; exit 0; }

log "==== IDQ post-reboot recovery started ===="

# Basic sanity checks
[[ -x "$INFA_SERVICE" ]] || die "infaservice.sh not found or not executable at: $INFA_SERVICE"

log "Sleeping ${SLEEP_AFTER_REBOOT}s after reboot..."
sleep "$SLEEP_AFTER_REBOOT"

# 1) Shutdown Informatica Services
log "Shutting down Informatica services..."
cd "$TOMCAT_BIN"
"$INFA_SERVICE" shutdown || log "Shutdown returned non-zero (continuing)."

# 2) Wait up to 5 mins for java processes to exit; then kill if needed
if wait_for_java_exit; then
  log "Shutdown clean."
else
  log "Shutdown wait exceeded; killing leftover IDQ java processes..."
  kill_leftover_java
fi

# 3) Cleanup directories (NOT deleting *.war files)
log "Cleaning Tomcat work/temp and exploded webapps (NOT deleting *.war files)..."

# tomcat/work/Catalina
safe_rm_dir "${TOMCAT_WORK}/Catalina"

# tomcat/temp/*
require_path_sane "$TOMCAT_TEMP"
if [[ -d "$TOMCAT_TEMP" ]]; then
  log "Removing contents of: $TOMCAT_TEMP"
  rm -rf --one-file-system "${TOMCAT_TEMP:?}/"* || true
fi

# isp/webapps exploded dirs only
for d in adminconsole csm ROOT coreservices; do
  safe_rm_dir "${ISP_WEBAPPS}/${d}"
done

# services/AdministratorConsole/webapps exploded dirs only
for d in adminhelp administrator adminconsole ows passwordchange ROOT monitoring; do
  safe_rm_dir "${ADMINCONSOLE_WEBAPPS}/${d}"
done

# services/work_dir (delete whole directory)
safe_rm_dir "${SERVICES_DIR}/work_dir"

# 4) Rotate node logs (node01 -> node01_old)
require_path_sane "$LOGS_DIR"
if [[ -d "${LOGS_DIR}/${NODE_NAME}_old" ]]; then
  log "Removing old log dir: ${LOGS_DIR}/${NODE_NAME}_old"
  rm -rf --one-file-system "${LOGS_DIR}/${NODE_NAME}_old"
fi
if [[ -d "${LOGS_DIR}/${NODE_NAME}" ]]; then
  log "Rotating logs: ${NODE_NAME} -> ${NODE_NAME}_old"
  mv "${LOGS_DIR}/${NODE_NAME}" "${LOGS_DIR}/${NODE_NAME}_old"
else
  log "Node log dir not found (skipping rotate): ${LOGS_DIR}/${NODE_NAME}"
fi

# 5) Start Informatica Services
log "Starting Informatica services..."
cd "$TOMCAT_BIN"
"$INFA_SERVICE" startup

log "==== IDQ post-reboot recovery completed ===="
exit 0
