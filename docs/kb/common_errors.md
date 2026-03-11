# Common Compile & Runtime Errors — Teensy/Arduino

## Compile Errors

| Error | Fix |
|---|---|
| 'xyz' was not declared in this scope | Missing #include, or function defined after first use — add forward declaration |
| redefinition of 'xyz' | Same function/variable in multiple files — use header guards (#pragma once) |
| expected ';' before ... | Missing semicolon on previous line |
| invalid conversion from 'const char*' to 'char*' | Add const to the pointer, or use strcpy to a mutable buffer |
| no matching function for call to ... | Wrong argument types or count — check function signature |
| multiple definition of 'xyz' | Define in one .cpp, declare extern in .h |
| lvalue required as left operand | Using = instead of == in condition, or assigning to const |
| ISO C++ forbids variable length array | Use malloc/new or fixed-size array — VLAs not standard C++ |

## Linker Errors

| Error | Fix |
|---|---|
| undefined reference to 'xyz' | Function declared but not defined — check .cpp file exists |
| multiple definition | Variable defined in header without extern — use extern in .h, define in one .cpp |

## Runtime Issues

| Symptom | Likely Cause |
|---|---|
| Crash/reboot loop | Stack overflow, null pointer, or ISR error |
| Hangs/freezes | Infinite loop, blocking call in ISR, or I2C bus lockup |
| Wrong values | Integer overflow, signed/unsigned mismatch, or uninitialized variable |
| Intermittent failures | Race condition with ISR, or floating input pin |
