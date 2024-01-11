KK Library
Version 20.0.0
Date    2023-09-06

K+K Messtechnik GmbH
http://www.kplusk-messtechnik.de
info@kplusk-messtechnik.de

Purpose of KK Library is control of and communication with K+K measuring cards

KK Library is available for Windows and Linux systems
Depending on platform, please use following KK Library:

1. Windows - 64 bit
Please copy KK_Library_64.dll into subdirectory System32 of your windows installation folder.
If 32 bit version of KK Library is needed, please copy KK_FX80E.dll into subdirectory SysWOW64 of your windows installation folder.

2. Windows - 32 bit
Please copy KK_FX80E.dll into subdirectory System32 of your windows installation folder.

3. Linux - general
It is usual on Linux systems to add version number to filename of shared object.
Therefore symbolic links are needed to select proper shared object version.
Please copy KK Library shared object into users shared object folder (maybe /usr/local/lib) and create symbolic link, if needed.

KK Library is available with two distinct calling conventions: stdcall and cdecl.
For python support cdecl is needed, Java needs stdcall.

4. Linux - 64 bit
stdcall: libkk_library_64.so.<version>
cdecL:   libkk_library_64_cdecl.so.<version>

5. Linux - 32 bit
stdcall: libkk_fx80e.so.<version>
cdecL:   libkk_library_32_cdecl.so.<version>
