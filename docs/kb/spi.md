# SPI Reference — Teensy 4.0

## Pins
- SPI (SPI0): SCK=13, MOSI=11, MISO=12
- SPI1: SCK=27, MOSI=26, MISO=1
- SPI2: SCK=46, MOSI=45, MISO=44 (Teensy 4.1 only)

## Basic Usage

```cpp
#include <SPI.h>

SPI.begin();
SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE0));
digitalWrite(CS_PIN, LOW);
uint8_t result = SPI.transfer(0x00);
digitalWrite(CS_PIN, HIGH);
SPI.endTransaction();
```

## Common Patterns
- Always use beginTransaction/endTransaction pairs
- Pull CS LOW before transfer, HIGH after
- For 16-bit: SPI.transfer16(value)
- For bulk: SPI.transfer(buffer, size)
- DMA: SPI has built-in EventResponder support for async transfers

## Common Errors
- "SPI has not been declared" → missing `#include <SPI.h>`
- Data corruption → check SPI_MODE (0-3) matches device datasheet
- Slow transfers → increase clock speed in SPISettings, or use DMA
