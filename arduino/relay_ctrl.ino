/**
 * ------------------------------------------------------------
 *  Proyecto: pi-hil-testing-utils
 *  Script:   relay_ctrl.ino
 *  Autor:    Franco Riba
 *
 *  Descripción:
 *    Control de un módulo de 6 relés mediante interfaz USB-Serial.
 *    Diseñado para pruebas automatizadas (HIL - Hardware-in-the-loop).
 *
 *  Hardware:
 *    - Arduino Nano (ATmega328P)
 *    - Módulo relé KY-019 de 6 canales
 *    - Conexión por USB (baudrate 115200)
 *
 *  Pines por defecto:
 *    IN1..IN6 -> D2..D7
 *
 *  Comandos disponibles por Serial:
 *    ON n       : enciende el relé n (0..5)
 *    OFF n      : apaga el relé n
 *    TOGGLE n   : cambia el estado del relé n
 *    PULSE n ms : enciende el relé n durante ms milisegundos
 *    ALLON      : enciende todos los relés
 *    ALLOFF     : apaga todos los relés
 *    STATUS     : imprime el estado de todos los relés
 *    HELP       : muestra ayuda
 *    ID         : identificación del dispositivo
 *
 *  Notas:
 *    - La mayoría de módulos son activos en bajo (LOW = ON).
 *    - Si tu módulo es activo en alto, cambia RELAY_ACTIVE_LOW a false.
 * ------------------------------------------------------------
 */

#include <Arduino.h>

// Configuración
constexpr bool RELAY_ACTIVE_LOW = true;        // true = activo-bajo, false = activo-alto
constexpr uint8_t RELAY_COUNT   = 6;           // cantidad de canales soportados
constexpr uint8_t RELAY_PINS[RELAY_COUNT] = {2, 3, 4, 5, 6, 7};

enum RelayState : uint8_t { R_OFF = 0, R_ON = 1 };
RelayState states[RELAY_COUNT];

/**
 * @brief Aplica el estado a un relé individual.
 */
void applyRelay(uint8_t ch, RelayState s) {
  if (ch >= RELAY_COUNT) return;
  states[ch] = s;

  // Activo-bajo: LOW = ON, HIGH = OFF
  if (RELAY_ACTIVE_LOW) {
    digitalWrite(RELAY_PINS[ch], (s == R_ON) ? LOW : HIGH);
  } else {
    digitalWrite(RELAY_PINS[ch], (s == R_ON) ? HIGH : LOW);
  }
}

/**
 * @brief Aplica el mismo estado a todos los relés.
 */
void allRelays(RelayState s) {
  for (uint8_t i = 0; i < RELAY_COUNT; i++) {
    applyRelay(i, s);
  }
}

/**
 * @brief Imprime el estado actual de todos los relés.
 */
void printStatus() {
  Serial.print(F("STATUS "));
  for (uint8_t i = 0; i < RELAY_COUNT; i++) {
    Serial.print(i);
    Serial.print(':');
    Serial.print(states[i] == R_ON ? F("ON") : F("OFF"));
    if (i < RELAY_COUNT - 1) Serial.print(' ');
  }
  Serial.println();
}

/**
 * @brief Muestra ayuda de comandos.
 */
void help() {
  Serial.println(F("Comandos disponibles:"));
  Serial.println(F("  ON n | OFF n | TOGGLE n | PULSE n ms"));
  Serial.println(F("  ALLON | ALLOFF | STATUS | HELP | ID"));
  Serial.println(F("  n=0..5, ms=milisegundos (1..60000)"));
}

void setup() {
  Serial.begin(115200);

  // Configurar pines como salida
  for (uint8_t i = 0; i < RELAY_COUNT; i++) {
    pinMode(RELAY_PINS[i], OUTPUT);
  }

  // Estado inicial seguro: todo apagado
  allRelays(R_OFF);

  Serial.println(F("OK RELAY-CTRL v1 (6ch) listo @115200"));
  help();
}

/**
 * @brief Lee una línea completa del puerto serial.
 */
bool readLine(String &out) {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') return true;
    if (out.length() < 64) out += c; // límite simple
  }
  return false;
}

/**
 * @brief Convierte string a entero con validación.
 */
int toIntSafe(const String &s, bool &ok) {
  if (s.length() == 0) { ok = false; return 0; }
  long v = s.toInt();
  ok = true;
  return (int)v;
}

void loop() {
  static String line;
  if (!readLine(line)) return;

  line.trim();
  line.toUpperCase();
  if (line.length() == 0) { line = ""; return; }

  // Tokenizar
  int sp1 = line.indexOf(' ');
  String cmd  = (sp1 < 0) ? line : line.substring(0, sp1);
  String rest = (sp1 < 0) ? ""   : line.substring(sp1 + 1);
  rest.trim();

  if (cmd == F("ON") || cmd == F("OFF") || cmd == F("TOGGLE")) {
    bool ok = false;
    int ch = toIntSafe(rest, ok);
    if (!ok || ch < 0 || ch >= RELAY_COUNT) {
      Serial.println(F("ERR canal inválido (0..5)"));
    } else {
      if (cmd == F("ON"))       applyRelay(ch, R_ON);
      else if (cmd == F("OFF")) applyRelay(ch, R_OFF);
      else                      applyRelay(ch, states[ch] == R_ON ? R_OFF : R_ON);
      printStatus();
    }
  } else if (cmd == F("PULSE")) {
    int sp = rest.indexOf(' ');
    if (sp < 0) {
      Serial.println(F("ERR uso: PULSE n ms"));
    } else {
      bool ok1 = false, ok2 = false;
      int ch = toIntSafe(rest.substring(0, sp), ok1);
      int ms = toIntSafe(rest.substring(sp + 1), ok2);
      if (!ok1 || !ok2 || ch < 0 || ch >= RELAY_COUNT || ms < 1 || ms > 60000) {
        Serial.println(F("ERR args (n=0..5, ms=1..60000)"));
      } else {
        applyRelay(ch, R_ON);
        delay(ms);
        applyRelay(ch, R_OFF);
        printStatus();
      }
    }
  } else if (cmd == F("ALLON")) {
    allRelays(R_ON); printStatus();
  } else if (cmd == F("ALLOFF")) {
    allRelays(R_OFF); printStatus();
  } else if (cmd == F("STATUS")) {
    printStatus();
  } else if (cmd == F("HELP")) {
    help();
  } else if (cmd == F("ID")) {
    Serial.println(F("RELAY-CTRL v1 (6ch)"));
  } else {
    Serial.println(F("ERR comando desconocido (try HELP)"));
  }

  line = "";
}
