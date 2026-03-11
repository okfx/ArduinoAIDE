# Interrupts Reference — Teensy 4.0

## External Interrupts
All digital pins support interrupts (unlike classic Arduino).

```cpp
attachInterrupt(digitalPinToInterrupt(pin), ISR_func, mode);
// mode: RISING, FALLING, CHANGE, LOW, HIGH

detachInterrupt(digitalPinToInterrupt(pin));
```

## IntervalTimer (Hardware Timers)
Teensy 4.0 has 4 PIT timers available.

```cpp
IntervalTimer myTimer;
myTimer.begin(callback, microseconds);  // periodic
myTimer.end();                           // stop
```

## ISR Rules
- Keep ISRs SHORT — no Serial.print, no delay, no malloc
- Use `volatile` for shared variables
- Use `noInterrupts()`/`interrupts()` to protect shared state
- Use atomic access for multi-byte shared variables

## Common Pattern — ISR + Flag

```cpp
volatile bool dataReady = false;

void myISR() { dataReady = true; }

void loop() {
  if (dataReady) {
    dataReady = false;
    // process data
  }
}
```

## Common Errors
- Crash/hang in ISR → doing too much work; set a flag and process in loop()
- Missed interrupts → ISR takes too long, overlapping triggers
- Corrupt shared data → forgot `volatile` keyword or atomic access
