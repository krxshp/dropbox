#define IR_SENSOR_PIN 4

bool previouslyDetected = false;

void setup() {
  Serial.begin(115200);
  pinMode(IR_SENSOR_PIN, INPUT);
}

void loop() {

  bool x = digitalRead(IR_SENSOR_PIN) == LOW;

  if (x && !previouslyDetected) {
    Serial.println("CARD_DETECTED");
  }

  previouslyDetected = x;
  delay(20);
}
