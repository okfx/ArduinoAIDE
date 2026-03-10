# Teensy 4.0 API Reference

## Digital I/O
```
pinMode(pin, mode)          — INPUT, OUTPUT, INPUT_PULLUP, INPUT_PULLDOWN, INPUT_DISABLE, OUTPUT_OPENDRAIN
digitalRead(pin)            — returns HIGH or LOW
digitalWrite(pin, val)      — set HIGH or LOW
digitalToggle(pin)          — flip pin state (Teensy extension)
digitalReadFast(pin)        — compile-time optimized read (pin must be constant)
digitalWriteFast(pin, val)  — compile-time optimized write
```

## Analog I/O
```
analogRead(pin)                  — read analog input (A0–A13 = pins 14–27)
analogReadResolution(bits)       — set ADC resolution: 10 (default), 12, or 13 bits
analogWrite(pin, val)            — PWM output (or DAC on pins A21/A22)
analogWriteResolution(bits)      — set PWM/DAC resolution: 8 (default), 10, 12, or 15 bits
analogWriteFrequency(pin, freq)  — set PWM frequency in Hz (default 488.28 Hz)
```

## Serial (USB + Hardware UARTs)
```
Serial                — USB Serial (CDC)
Serial1–Serial8       — hardware UARTs
  Serial1: TX=1,  RX=0
  Serial2: TX=8,  RX=7
  Serial3: TX=14, RX=15
  Serial4: TX=17, RX=16
  Serial5: TX=20, RX=21
  Serial6: TX=24, RX=25
  Serial7: TX=29, RX=28

.begin(baud)          — initialize at baud rate
.begin(baud, format)  — format: SERIAL_8N1 (default), SERIAL_8E1, SERIAL_8O1, etc.
.available()          — bytes available to read
.read()               — read one byte (-1 if none)
.readBytes(buf, len)  — read up to len bytes into buffer
.write(data)          — write byte(s)
.print() / .println() — formatted output
.flush()              — wait for transmit complete
.setTimeout(ms)       — timeout for readBytes/readString
```

## Timing
```
delay(ms)                  — blocking delay in milliseconds
delayMicroseconds(us)      — blocking delay in microseconds
millis()                   — milliseconds since boot (unsigned long)
micros()                   — microseconds since boot (unsigned long)
elapsedMillis varName      — auto-incrementing ms counter (non-blocking)
elapsedMicros varName      — auto-incrementing us counter (non-blocking)
```

## IntervalTimer (Hardware Timers)
```
IntervalTimer myTimer;
myTimer.begin(callback, microseconds)  — start repeating timer
myTimer.end()                          — stop timer
myTimer.priority(level)                — set interrupt priority (0=highest, 255=lowest)
```
Up to 4 IntervalTimers can run simultaneously. Callbacks run in ISR context.

## SPI
```
#include <SPI.h>
SPI.begin()                             — initialize SPI (default: SCK=13, MOSI=11, MISO=12)
SPI.beginTransaction(SPISettings(freq, MSBFIRST, SPI_MODE0))
SPI.transfer(data)                      — send/receive one byte
SPI.transfer(buf, count)                — send/receive buffer
SPI.endTransaction()
SPI.setSCK(pin)                         — alternate SCK pin (e.g., 14 for SPI0)
SPI.setMOSI(pin)                        — alternate MOSI pin
SPI.setMISO(pin)                        — alternate MISO pin
SPI1, SPI2                              — additional SPI buses
```

## I2C (Wire)
```
#include <Wire.h>
Wire.begin()                    — initialize as controller
Wire.begin(address)             — initialize as peripheral
Wire.setClock(freq)             — set clock: 100000, 400000, 1000000, 3400000
Wire.beginTransmission(addr)    — start write to device
Wire.write(data)                — queue data
Wire.endTransmission()          — send queued data, returns status
Wire.requestFrom(addr, count)   — request bytes from device
Wire.available()                — bytes available after requestFrom
Wire.read()                     — read one byte
Wire1, Wire2                    — additional I2C buses
  Wire:  SDA=18, SCL=19
  Wire1: SDA=17, SCL=16
  Wire2: SDA=25, SCL=24
```

## EEPROM
```
#include <EEPROM.h>
EEPROM.read(addr)               — read one byte (addr: 0–1079 on Teensy 4.0)
EEPROM.write(addr, val)         — write one byte (emulated in flash, ~100K write cycles)
EEPROM.update(addr, val)        — write only if value differs
EEPROM.get(addr, variable)      — read any data type
EEPROM.put(addr, variable)      — write any data type
EEPROM.length()                 — total bytes available (1080)
```

## Audio Library
```
#include <Audio.h>
AudioInputI2S          — I2S audio input
AudioOutputI2S         — I2S audio output
AudioInputAnalog       — analog audio input via ADC
AudioOutputAnalog      — analog audio output via DAC
AudioSynthWaveform     — waveform generator (sine, saw, square, triangle, pulse, etc.)
AudioSynthWaveformDc   — DC level generator
AudioEffectEnvelope    — ADSR envelope
AudioFilterStateVariable — state variable filter (LP, BP, HP)
AudioMixer4            — 4-input mixer
AudioConnection        — patch cord between audio objects
AudioControlSGTL5000   — Audio Shield codec control

// Typical audio setup:
AudioSynthWaveform waveform;
AudioOutputI2S audioOut;
AudioConnection patchCord(waveform, 0, audioOut, 0);
AudioControlSGTL5000 codec;

void setup() {
  AudioMemory(20);
  codec.enable();
  codec.volume(0.5);
  waveform.begin(WAVEFORM_SINE);
  waveform.frequency(440);
  waveform.amplitude(0.5);
}
```

## USB Types
```
// Set in Tools > USB Type:
// Serial                 — USB CDC Serial only
// Serial + Keyboard      — HID keyboard + serial
// Serial + Keyboard + Mouse + Joystick — full HID
// MIDI                   — USB MIDI device
// Audio                  — USB Audio device
// Serial + MIDI          — serial + MIDI

// USB MIDI:
usbMIDI.sendNoteOn(note, velocity, channel)
usbMIDI.sendNoteOff(note, velocity, channel)
usbMIDI.sendControlChange(control, value, channel)
usbMIDI.read()              — process incoming MIDI
usbMIDI.setHandleNoteOn(callback)
```

## DMA
```
#include <DMAChannel.h>
DMAChannel myDMA;
myDMA.sourceBuffer(src, len)       — set source buffer
myDMA.destinationBuffer(dst, len)  — set destination buffer
myDMA.transferSize(bytes)          — bytes per transfer (1, 2, or 4)
myDMA.transferCount(n)             — number of transfers
myDMA.triggerAtHardwareEvent(src)  — trigger source (e.g., DMAMUX_SOURCE_ADC1)
myDMA.enable()                     — start DMA
myDMA.attachInterrupt(callback)    — call on completion
myDMA.clearInterrupt()             — clear interrupt flag in callback
```

## Interrupts
```
attachInterrupt(digitalPinToInterrupt(pin), callback, mode)
  — mode: RISING, FALLING, CHANGE, LOW, HIGH
detachInterrupt(digitalPinToInterrupt(pin))
noInterrupts()              — disable all interrupts
interrupts()                — re-enable interrupts
NVIC_SET_PRIORITY(irq, p)   — set interrupt priority (ARM-level)
```

## Teensy-Specific Extensions
```
ARM_DWT_CYCCNT              — cycle counter (600M cycles/sec at 600 MHz)
F_CPU                       — CPU frequency in Hz (600000000)
CORE_PIN0_PORTREG           — direct port register access
teensy_serial_number         — unique serial number
CrashReport                 — crash dump after reboot
```
