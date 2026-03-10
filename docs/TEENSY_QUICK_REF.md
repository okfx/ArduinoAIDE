# Teensy 4.0 Quick Reference

## Board Specifications
- **MCU:** NXP i.MX RT1062, ARM Cortex-M7 @ 600 MHz
- **Flash:** 2 MB
- **RAM:** 1 MB total, including 512 KB tightly coupled RAM
- **FQBN:** `teensy:avr:teensy40`
- **Logic level:** 3.3V only, pins are **not** 5V tolerant
- **Digital pins:** 0 to 39
- **Analog inputs:** `A0` to `A13` (pins 14 to 27), 10-bit by default, up to 12-bit
- **PWM pins:** 0 to 15, 18 to 19, 22 to 25, 28 to 29, 33, 36 to 37
- **DAC pins:** `A21` (pin 25), `A22` (pin 26), 12-bit output

## Core APIs
- `Serial`  
  USB serial interface. No external pins required.
- `Serial1` to `Serial8`  
  Hardware UART interfaces.
- `analogReadResolution(bits)`  
  Sets ADC resolution, typically 10 or 12 bits.
- `analogWriteResolution(bits)`  
  Sets PWM or DAC output resolution, typically 8, 10, or 12 bits.
- `analogWriteFrequency(pin, freq)`  
  Sets PWM frequency for a pin.
- `IntervalTimer`  
  Hardware timer for microsecond-scale periodic callbacks.
- `elapsedMillis` / `elapsedMicros`  
  Auto-incrementing timing helpers for non-blocking code.
- `Bounce`  
  Debounce helper library. Include with `#include <Bounce.h>`.

## Common Patterns

### IntervalTimer
```cpp
IntervalTimer myTimer;

void timerCallback() {
  // ISR context: keep this short
}

void setup() {
  myTimer.begin(timerCallback, 1000);  // 1000 us = 1 ms
}
```

### elapsedMillis
```cpp
elapsedMillis sinceLastUpdate;

void loop() {
  if (sinceLastUpdate >= 100) {
    sinceLastUpdate = 0;
    // do work every 100 ms
  }
}
```

### High-resolution ADC read
```cpp
analogReadResolution(12);  // range: 0 to 4095
int val = analogRead(A0);
```

## Important Gotchas
- `delay()` blocks execution. Use `elapsedMillis` or `elapsedMicros` for non-blocking timing.
- ISR callbacks must be fast. Avoid `Serial.print()`, dynamic allocation, and `delay()`.
- `LED_BUILTIN` is pin 13.
- `analogWrite()` produces PWM, not true analog output, except on DAC pins.
- USB serial may not be ready immediately at boot. In `setup()`, use `while (!Serial)` if needed.
- Teensy 4.0 is a 3.3V board. Use level shifting for 5V peripherals.