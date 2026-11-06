#include <Arduino.h>

// Estructura para almacenar las velocidades resultantes de cada rueda
struct MecanumOutputs {
  float fl; // Front-Left
  float fr; // Front-Right
  float rl; // Rear-Left
  float rr; // Rear-Right
};

// Cinemática inversa de ruedas Mecanum
MecanumOutputs computeMecanum(float Vx, float Vy, float omega) {
  MecanumOutputs out;
  
  // Cálculo de componentes individuales
  out.fl = Vx + Vy + omega;
  out.fr = Vx - Vy - omega;
  out.rl = Vx - Vy + omega;
  out.rr = Vx + Vy - omega;

  // Normalización proporcional para no superar la escala [-1.0, 1.0]
  float maxVal = fmax(fabs(out.fl), fmax(fabs(out.fr), fmax(fabs(out.rl), fabs(out.rr))));
  if (maxVal > 1.0f) {
    out.fl /= maxVal;
    out.fr /= maxVal;
    out.rl /= maxVal;
    out.rr /= maxVal;
  }

  return out;
}

// Analiza el vector de velocidades para deducir el estado cinemático real
void printSimulatedMotion(float Vx, float Vy, float omega) {
  MecanumOutputs wheels = computeMecanum(Vx, Vy, omega);

  Serial.println("========================================");
  
  // Detección de la maniobra según consignas
  if (Vx > 0 && Vy == 0 && omega == 0) {
    Serial.println("ESTADO: Avanzando hacia adelante [^]");
  } else if (Vx < 0 && Vy == 0 && omega == 0) {
    Serial.println("ESTADO: Retrocediendo hacia atras [v]");
  } else if (Vx == 0 && Vy > 0 && omega == 0) {
    Serial.println("ESTADO: Desplazamiento lateral a la DERECHA [>]");
  } else if (Vx == 0 && Vy < 0 && omega == 0) {
    Serial.println("ESTADO: Desplazamiento lateral a la IZQUIERDA [<]");
  } else if (Vx == 0 && Vy == 0 && omega > 0) {
    Serial.println("ESTADO: Giro sobre su eje horario (CW)");
  } else if (Vx == 0 && Vy == 0 && omega < 0) {
    Serial.println("ESTADO: Giro sobre su eje antihorario (CCW)");
  } else if (Vx == 0 && Vy == 0 && omega == 0) {
    Serial.println("ESTADO: Robot detenido [STOP]");
  } else {
    Serial.println("ESTADO: Movimiento compuesto / diagonal");
  }

  // Verificación de consigna en cada rueda
  Serial.print("  Rueda Delantera Izq  (FL): "); Serial.println(wheels.fl, 2);
  Serial.print("  Rueda Delantera Der  (FR): "); Serial.println(wheels.fr, 2);
  Serial.print("  Rueda Trasera   Izq  (RL): "); Serial.println(wheels.rl, 2);
  Serial.print("  Rueda Trasera   Der  (RR): "); Serial.println(wheels.rr, 2);
  Serial.println("========================================\n");
}

void setup() {
  Serial.begin(115200);
  while (!Serial) {
    ; // Espera a que abra el monitor serie
  }

  Serial.println("--- SIMULADOR DE TRACCION MECANUM INICIADO ---");
  Serial.println("Controles (escribe en el monitor serie y pulsa Enter):");
  Serial.println(" [w] -> Avanzar adelante");
  Serial.println(" [s] -> Retroceder atras");
  Serial.println(" [d] -> Mover lateral a la derecha");
  Serial.println(" [a] -> Mover lateral a la izquierda");
  Serial.println(" [e] -> Giro horario");
  Serial.println(" [q] -> Giro antihorario");
  Serial.println(" [x] -> Detener robot\n");
}

void loop() {
  if (Serial.available() > 0) {
    char key = Serial.read();

    switch (key) {
      case 'w':
      case 'W':
        printSimulatedMotion(1.0, 0.0, 0.0);
        break;

      case 's':
      case 'S':
        printSimulatedMotion(-1.0, 0.0, 0.0);
        break;

      case 'd':
      case 'D':
        printSimulatedMotion(0.0, 1.0, 0.0);
        break;

      case 'a':
      case 'A':
        printSimulatedMotion(0.0, -1.0, 0.0);
        break;

      case 'e':
      case 'E':
        printSimulatedMotion(0.0, 0.0, 1.0);
        break;

      case 'q':
      case 'Q':
        printSimulatedMotion(0.0, 0.0, -1.0);
        break;

      case 'x':
      case 'X':
      case ' ':
        printSimulatedMotion(0.0, 0.0, 0.0);
        break;

      // Ignora saltos de línea y retorno de carro del monitor serie
      case '\r':
      case '\n':
        break;

      default:
        Serial.print("Comando no reconocido: '");
        Serial.print(key);
        Serial.println("'. Usa W, A, S, D, Q, E o X.");
        break;
    }
  }
}