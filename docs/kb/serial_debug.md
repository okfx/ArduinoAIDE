# Serial Debugging Reference — Teensy 4.0

## USB Serial

```cpp
Serial.begin(115200);  // baud rate ignored for USB, but conventional
while (!Serial && millis() < 3000) {}  // wait up to 3s for USB connection
```

## Formatted Output

```cpp
Serial.printf("value: %d, float: %.2f, hex: 0x%04X\n", val, fval, hval);
Serial.print(val, HEX);   // print in hex
Serial.print(val, BIN);   // print in binary
```

## Hardware UARTs

```cpp
Serial1.begin(9600);  // TX=1, RX=0
Serial2.begin(9600);  // TX=8, RX=7
// ... up to Serial8
```

## Common Patterns

```cpp
// Timestamp every line
Serial.printf("[%lu] sensor: %d\n", millis(), reading);

// CSV for Serial Plotter
Serial.printf("%d,%d,%d\n", sensor1, sensor2, sensor3);
```

## Common Errors
- No output → forgot `while(!Serial)` wait, or USB cable is charge-only
- Garbled output → baud rate mismatch on hardware UART
- Buffer overflow → `Serial.availableForWrite()` to check before large writes
