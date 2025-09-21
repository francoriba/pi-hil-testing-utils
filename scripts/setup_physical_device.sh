#!/bin/bash
# Setup GL-MT300N-V2

set -e

readonly OPENWRT_TESTS_DIR="/home/franco/pi/openwrt-23.05.5/tests"
readonly UTILS_DIR="/home/franco/pi/pi-hil-testing-utils"
readonly ARDUINO_SCRIPT="$UTILS_DIR/scripts/arduino_relay_control.py"
readonly CHECK_SCRIPT="$UTILS_DIR/scripts/check_router_serial_conn.py"

readonly POWER_RELAY_CHANNEL=0
readonly SERIAL_RELAY_CHANNEL=1
readonly ROUTER_PORT="/dev/glinet-mango"
readonly BAUDRATE=115200
readonly WAIT_AFTER_POWER=10
readonly WAIT_AFTER_SERIAL=3

log()  { printf '%s\n' "$*"; }
ok()   { printf '✔ %s\n' "$*"; }
warn() { printf '… %s\n' "$*" >&2; }
err()  { printf '✖ %s\n' "$*" >&2; }

check_arduino() {
  log "Arduino…"
  [[ -e "/dev/arduino-relay" ]] || { err "/dev/arduino-relay no existe"; exit 1; }
  command -v python3 >/dev/null || { err "python3 no disponible"; exit 1; }
  python3 "$ARDUINO_SCRIPT" status || { err "Arduino no responde"; exit 1; }
  ok "Arduino OK"
}

check_serial_port() {
  log "Serial…"
  [[ -e "$ROUTER_PORT" ]] || { err "$ROUTER_PORT no existe"; exit 1; }
  ok "Serial OK"
}

power_on_sequence() {
  log "Power seq…"
  python3 "$ARDUINO_SCRIPT" on  "$POWER_RELAY_CHANNEL"
  python3 "$ARDUINO_SCRIPT" on  "$SERIAL_RELAY_CHANNEL"
  sleep 3
  python3 "$ARDUINO_SCRIPT" off "$POWER_RELAY_CHANNEL"
  sleep "$WAIT_AFTER_POWER"
  python3 "$ARDUINO_SCRIPT" off "$SERIAL_RELAY_CHANNEL"
  sleep "$WAIT_AFTER_SERIAL"
  ok "Power seq OK"
}

test_serial_comm() {
  log "Comms…"
  [[ -f "$CHECK_SCRIPT" ]] || { err "Falta $CHECK_SCRIPT"; exit 1; }
  if python3 "$CHECK_SCRIPT" "$ROUTER_PORT" --baudrate "$BAUDRATE"; then
    ok "Comms OK"
  else
    warn "Comms no verificadas (continuo)"
  fi
}

verify_deps() {
  log "Deps…"
  command -v uv >/dev/null || { err "Falta uv (curl -LsSf https://astral.sh/uv/install.sh | sh)"; exit 1; }
  if [[ -d "$OPENWRT_TESTS_DIR" ]]; then
    pushd "$OPENWRT_TESTS_DIR/.." >/dev/null
    make tests/setup || warn "make tests/setup falló (continuo)"
    popd >/dev/null
  else
    warn "No existe $OPENWRT_TESTS_DIR"
  fi
  ok "Deps OK"
}

verify_target_config() {
  log "Target…"
  [[ -f "$OPENWRT_TESTS_DIR/targets/gl-mt300n-v2.yaml" ]] || { err "Falta targets/gl-mt300n-v2.yaml"; exit 1; }
  # [[ -f "$OPENWRT_TESTS_DIR/drivers/arduino_power_driver.py" ]] || { err "Falta drivers/arduino_power_driver.py"; exit 1; }
  ok "Target OK"
}

summary() {
  printf '\n'
  ok "Setup listo"
  printf 'Relés: power=%s, serial=%s\n' "$POWER_RELAY_CHANNEL" "$SERIAL_RELAY_CHANNEL"
  printf 'Run: cd %s/.. && make tests/gl-mt300n-v2 V=s\n' "$OPENWRT_TESTS_DIR"
}

main() {
  printf '== GL-MT300N-V2 Setup ==\n'
  check_arduino
  check_serial_port
  power_on_sequence
  test_serial_comm
  verify_deps
  verify_target_config
  summary
}

main "$@"
