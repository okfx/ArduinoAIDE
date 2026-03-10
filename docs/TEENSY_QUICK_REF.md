# Teensy 4.0 Quick Reference

## Board Specs
- MCU: NXP iMXRT1062 (ARM Cortex-M7, 600 MHz)
- Flash: 2 MB, RAM: 1 MB (512K tightly coupled)
- FQBN: `teensy:avr:teensy40`
- Digital pins: 0–39 (3.3V logic, NOT 5V tolerant)
- Analog inputs: A0–A13 (pins 14–27), 10-bit default, up to 12-bit
- PWM: pins 0–15, 18–19, 22–25, 28–29, 33, 36–37
- DAC: A21 (pin 25), A22 (pin 26) — 12-bit

## Key APIs
- `Serial` — USB Serial (always available, no pin needed)
- `Serial1`–`Serial8` — hardware UARTs
- `analogReadResolution(bits)` — set ADC to 10/12 bits
- `analogWriteResolution(bits)` — set PWM/DAC to 8/10/12 bits
- `analogWriteFrequency(pin, freq)` — set PWM frequency
- `IntervalTimer` — hardware timer with microsecond callbacks
- `elapsedMillis` / `elapsedMicros` — auto-incrementing time variables
- `Bounce` — debounce library (include `<Bounce.h>`)

## Common Patterns
```cpp
// IntervalTimer
IntervalTimer myTimer;
void timerCallback() { /* ISR context — keep short */ }
void setup() { myTimer.begin(timerCallback, 1000); } // 1ms

// elapsedMillis
elapsedMillis sinceLastUpdate;
if (sinceLastUpdate >= 100) { sinceLastUpdate = 0; /* do work */ }

// ADC high resolution
analogReadResolution(12);  // 0–4095
int val = analogRead(A0);
```

## Important Gotchas
- `delay()` blocks everything — use `elapsedMillis` for non-blocking timing
- ISR callbacks must be fast — no Serial.print, no malloc, no delay
- Pin 13 = LED_BUILTIN
- `analogWrite()` is PWM (not true analog) except on DAC pins
- USB Serial may not be ready at boot — use `while (!Serial)` in setup if needed
- Teensy 4.0 runs at 3.3V — level shifters needed for 5V peripherals
