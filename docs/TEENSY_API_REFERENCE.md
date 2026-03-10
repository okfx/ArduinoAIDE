# Teensy 4.0 API Reference

## Digital I/O
```cpp
pinMode(pin, mode)          // INPUT, OUTPUT, INPUT_PULLUP, INPUT_PULLDOWN, INPUT_DISABLE, OUTPUT_OPENDRAIN
digitalRead(pin)            // returns HIGH or LOW
digitalWrite(pin, val)      // sets HIGH or LOW
digitalToggle(pin)          // toggles pin state (Teensy extension)
digitalReadFast(pin)        // compile-time optimized read, pin must be constant
digitalWriteFast(pin, val)  // compile-time optimized write, pin must be constant
```

## Analog I/O
```cpp
analogRead(pin)                  // reads analog input, A0 to A13 = pins 14 to 27
analogReadResolution(bits)       // ADC resolution: 10 (default), 12, or 13 bits
analogWrite(pin, val)            // PWM output, or DAC on pins A21 and A22
analogWriteResolution(bits)      // PWM or DAC resolution: 8 (default), 10, 12, or 15 bits
analogWriteFrequency(pin, freq)  // PWM frequency in Hz, default 488.28 Hz
```

## Serial (USB and Hardware UARTs)
```cpp
Serial                // USB Serial (CDC)
Serial1 to Serial8    // hardware UARTs

// UART pin mappings
Serial1   // TX=1,  RX=0
Serial2   // TX=8,  RX=7
Serial3   // TX=14, RX=15
Serial4   // TX=17, RX=16
Serial5   // TX=20, RX=21
Serial6   // TX=24, RX=25
Serial7   // TX=29, RX=28

.begin(baud)          // initialize at baud rate
.begin(baud, format)  // format examples: SERIAL_8N1, SERIAL_8E1, SERIAL_8O1
.available()          // bytes available to read
.read()               // reads one byte, returns -1 if none
.readBytes(buf, len)  // reads up to len bytes into buffer
.write(data)          // writes byte or bytes
.print()              // formatted output
.println()            // formatted output with newline
.flush()              // waits for transmit complete
.setTimeout(ms)       // timeout for readBytes and readString
```

## Timing
```cpp
delay(ms)                  // blocking delay in milliseconds
delayMicroseconds(us)      // blocking delay in microseconds
millis()                   // milliseconds since boot, unsigned long
micros()                   // microseconds since boot, unsigned long
elapsedMillis varName      // auto-incrementing millisecond counter
elapsedMicros varName      // auto-incrementing microsecond counter
```

## IntervalTimer
```cpp
IntervalTimer myTimer;
myTimer.begin(callback, microseconds)  // starts repeating timer
myTimer.end()                          // stops timer
myTimer.priority(level)                // interrupt priority, 0 = highest, 255 = lowest
```

Up to 4 `IntervalTimer` instances can run simultaneously. Callbacks execute in ISR context.

## SPI
```cpp
#include <SPI.h>

SPI.begin()                             // default pins: SCK=13, MOSI=11, MISO=12
SPI.beginTransaction(SPISettings(freq, MSBFIRST, SPI_MODE0))
SPI.transfer(data)                      // sends and receives one byte
SPI.transfer(buf, count)                // sends and receives a buffer
SPI.endTransaction()
SPI.setSCK(pin)                         // set alternate SCK pin
SPI.setMOSI(pin)                        // set alternate MOSI pin
SPI.setMISO(pin)                        // set alternate MISO pin

SPI1                                    // additional SPI bus
SPI2                                    // additional SPI bus
```

## I2C (Wire)
```cpp
#include <Wire.h>

Wire.begin()                    // initialize as controller
Wire.begin(address)             // initialize as peripheral
Wire.setClock(freq)             // 100000, 400000, 1000000, or 3400000
Wire.beginTransmission(addr)    // starts write to device
Wire.write(data)                // queues data
Wire.endTransmission()          // sends queued data, returns status
Wire.requestFrom(addr, count)   // requests bytes from device
Wire.available()                // bytes available after requestFrom
Wire.read()                     // reads one byte

Wire1                           // additional I2C bus
Wire2                           // additional I2C bus

// I2C pin mappings
Wire   // SDA=18, SCL=19
Wire1  // SDA=17, SCL=16
Wire2  // SDA=25, SCL=24
```

## EEPROM
```cpp
#include <EEPROM.h>

EEPROM.read(addr)           // reads one byte, addr 0 to 1079
EEPROM.write(addr, val)     // writes one byte, flash-emulated
EEPROM.update(addr, val)    // writes only if value differs
EEPROM.get(addr, variable)  // reads any data type
EEPROM.put(addr, variable)  // writes any data type
EEPROM.length()             // total bytes available, 1080
```

## Audio Library
```cpp
#include <Audio.h>

AudioInputI2S               // I2S audio input
AudioOutputI2S              // I2S audio output
AudioInputAnalog            // analog audio input via ADC
AudioOutputAnalog           // analog audio output via DAC
AudioSynthWaveform          // sine, saw, square, triangle, pulse, etc.
AudioSynthWaveformDc        // DC level generator
AudioEffectEnvelope         // ADSR envelope
AudioFilterStateVariable    // low-pass, band-pass, high-pass filter
AudioMixer4                 // 4-input mixer
AudioConnection             // patch cord between audio objects
AudioControlSGTL5000        // Audio Shield codec control

// Typical setup
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
```cpp
// Set in Tools > USB Type

// Serial
// Serial + Keyboard
// Serial + Keyboard + Mouse + Joystick
// MIDI
// Audio
// Serial + MIDI

// USB MIDI
usbMIDI.sendNoteOn(note, velocity, channel);
usbMIDI.sendNoteOff(note, velocity, channel);
usbMIDI.sendControlChange(control, value, channel);
usbMIDI.read();                    // process incoming MIDI
usbMIDI.setHandleNoteOn(callback);
```

## DMA
```cpp
#include <DMAChannel.h>

DMAChannel myDMA;
myDMA.sourceBuffer(src, len)       // sets source buffer
myDMA.destinationBuffer(dst, len)  // sets destination buffer
myDMA.transferSize(bytes)          // bytes per transfer: 1, 2, or 4
myDMA.transferCount(n)             // number of transfers
myDMA.triggerAtHardwareEvent(src)  // trigger source, for example DMAMUX_SOURCE_ADC1
myDMA.enable()                     // starts DMA
myDMA.attachInterrupt(callback)    // callback on completion
myDMA.clearInterrupt()             // clear interrupt flag in callback
```

## Interrupts
```cpp
attachInterrupt(digitalPinToInterrupt(pin), callback, mode);
// mode: RISING, FALLING, CHANGE, LOW, HIGH

detachInterrupt(digitalPinToInterrupt(pin));
noInterrupts();            // disables all interrupts
interrupts();              // re-enables interrupts
NVIC_SET_PRIORITY(irq, p); // sets ARM interrupt priority
```

## Teensy-Specific Extensions
```cpp
ARM_DWT_CYCCNT       // cycle counter
F_CPU                // CPU frequency in Hz
CORE_PIN0_PORTREG    // direct port register access
teensy_serial_number // unique serial number
CrashReport          // crash dump after reboot
```