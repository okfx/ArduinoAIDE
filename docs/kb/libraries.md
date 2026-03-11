# Common Teensy Libraries Quick Reference

## Audio (Teensy Audio Library)

```cpp
#include <Audio.h>
```
- Audio System Design Tool: https://www.pjrc.com/teensy/gui/
- Use AudioConnection objects to wire components
- `AudioMemory(12);` in setup()

## Servo

```cpp
#include <Servo.h>
Servo myservo;
myservo.attach(pin);
myservo.write(angle);          // 0-180 degrees
myservo.writeMicroseconds(us); // 1000-2000
```

## AccelStepper

```cpp
#include <AccelStepper.h>
AccelStepper stepper(AccelStepper::DRIVER, stepPin, dirPin);
stepper.setMaxSpeed(1000);
stepper.setAcceleration(500);
stepper.moveTo(position);
stepper.run();  // call in loop()
```

## Adafruit_NeoPixel / WS2812

```cpp
#include <Adafruit_NeoPixel.h>
Adafruit_NeoPixel strip(NUM_LEDS, PIN, NEO_GRB + NEO_KHZ800);
strip.begin();
strip.setPixelColor(i, strip.Color(r, g, b));
strip.show();
```

## Encoder

```cpp
#include <Encoder.h>
Encoder myEnc(pinA, pinB);  // best: both pins have interrupt capability
long position = myEnc.read();
```

## SD Card

```cpp
#include <SD.h>
SD.begin(BUILTIN_SDCARD);  // Teensy 4.1 built-in SD
File f = SD.open("data.csv", FILE_WRITE);
f.println(data);
f.close();
```
