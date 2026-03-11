# I2C (Wire) Reference — Teensy 4.0

## Pins
- Wire (I2C0): SDA=18, SCL=19 (4.7k pullups recommended)
- Wire1: SDA=17, SCL=16
- Wire2: SDA=25, SCL=24

## Basic Usage

```cpp
#include <Wire.h>

Wire.begin();            // controller mode
Wire.setClock(400000);   // 400 kHz fast mode

// Read from device
Wire.beginTransmission(0x68);
Wire.write(regAddr);
Wire.endTransmission(false);  // repeated start
Wire.requestFrom(0x68, 2);
uint8_t hi = Wire.read();
uint8_t lo = Wire.read();

// Write to device
Wire.beginTransmission(0x68);
Wire.write(regAddr);
Wire.write(value);
Wire.endTransmission();
```

## Common Errors
- "Wire was not declared" → missing `#include <Wire.h>`
- No response → check pullup resistors, verify address with I2C scanner
- endTransmission returns non-zero → device not responding or bus stuck
- Hanging → bus lockup; add `Wire.setDefaultTimeout(10000)` (Teensy extension)

## I2C Scanner Pattern

```cpp
for (byte addr = 1; addr < 127; addr++) {
  Wire.beginTransmission(addr);
  if (Wire.endTransmission() == 0) {
    Serial.printf("Found device at 0x%02X\n", addr);
  }
}
```
