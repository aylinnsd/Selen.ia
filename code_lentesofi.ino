// Arduino de los LENTES (receptor)
const int buzzerPin = 3;
const bool BUZZER_ES_PASIVO = true; // true = tone(); false = activo HIGH/LOW
const int  FREQ_HZ = 3000;

unsigned long lastMsgMs = 0;
const unsigned long TIMEOUT_MS = 3000; // si no llega nada en 3s, apaga por seguridad

void setup() {
  pinMode(buzzerPin, OUTPUT);
  if (!BUZZER_ES_PASIVO) digitalWrite(buzzerPin, LOW);
  Serial.begin(115200);
}

void buzzerOn() {
  if (BUZZER_ES_PASIVO) tone(buzzerPin, FREQ_HZ);
  else digitalWrite(buzzerPin, HIGH);
}

void buzzerOff() {
  if (BUZZER_ES_PASIVO) noTone(buzzerPin);
  else digitalWrite(buzzerPin, LOW);
}

void loop() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '1') {
      buzzerOn();
      lastMsgMs = millis();
    } else if (c == '0') {
      buzzerOff();
      lastMsgMs = millis();
    }
  }
  if (millis() - lastMsgMs > TIMEOUT_MS) {
    buzzerOff();
  }
}
