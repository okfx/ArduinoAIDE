# Memory Management — Teensy 4.0

## Memory Layout
- Flash: 2 MB (program storage)
- RAM1 (DTCM): 512 KB — stack, heap, global variables
- RAM2 (OCRAM): 512 KB — DMAMEM, EXTMEM overflow

## PROGMEM / F() Macro

```cpp
const char msg[] PROGMEM = "Hello";  // store in flash
Serial.println(F("Stored in flash"));  // F() macro for string literals
```

## DMAMEM

```cpp
DMAMEM uint8_t buffer[4096];  // allocate in RAM2
```

## Checking Memory Usage

```cpp
extern unsigned long _heap_start;
extern unsigned long _heap_end;
extern char *__brkval;

int freeRam() {
  char top;
  return &top - __brkval;
}
```

## Common Errors
- Stack overflow → large local arrays; move to global or DMAMEM
- Out of RAM1 → move large buffers to DMAMEM
- Fragmentation → avoid dynamic allocation in loop(); pre-allocate
- String duplication → use F() macro for string literals
