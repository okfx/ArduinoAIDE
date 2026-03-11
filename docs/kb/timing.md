# Timing & Non-Blocking Patterns — Teensy 4.0

## elapsedMillis / elapsedMicros
Auto-incrementing timers — no manual tracking needed.

```cpp
elapsedMillis sinceUpdate;

void loop() {
  if (sinceUpdate >= 100) {
    sinceUpdate = 0;
    updateSensors();
  }
}
```

## millis() / micros()
- `millis()` returns ms since startup (wraps at ~50 days)
- `micros()` returns us since startup (wraps at ~70 minutes)

## Non-Blocking Pattern (replace delay())

```cpp
unsigned long previousMillis = 0;
const long interval = 1000;

void loop() {
  unsigned long now = millis();
  if (now - previousMillis >= interval) {
    previousMillis = now;
    doThing();
  }
}
```

## Common Errors
- Using `delay()` in code that needs responsiveness → use elapsedMillis
- millis() overflow bug → use subtraction (`now - previous >= interval`), NOT (`now >= previous + interval`)
- micros() resolution is 1us on Teensy 4.0 (much better than classic Arduino's 4us)
