# Copied and adapted from:
# https://github.com/microsoft/vcpkg/blob/7adc2e4d49e8d0efc07a369079faa6bc3dbb90f3/scripts/toolchains/linux.cmake
#
# The original seems to be written only for GCC.  This version is changed to use clang and
# LLVM bin tools.

if(NOT _VCPKG_LINUX_CLANG_TOOLCHAIN)
    set(_VCPKG_LINUX_CLANG_TOOLCHAIN 1)

    if(POLICY CMP0056)
        cmake_policy(SET CMP0056 NEW)
    endif()
    if(POLICY CMP0066)
        cmake_policy(SET CMP0066 NEW)
    endif()
    if(POLICY CMP0067)
        cmake_policy(SET CMP0067 NEW)
    endif()
    if(POLICY CMP0137)
        cmake_policy(SET CMP0137 NEW)
    endif()
    list(APPEND CMAKE_TRY_COMPILE_PLATFORM_VARIABLES
        VCPKG_CRT_LINKAGE VCPKG_TARGET_ARCHITECTURE
        VCPKG_C_FLAGS VCPKG_CXX_FLAGS
        VCPKG_C_FLAGS_DEBUG VCPKG_CXX_FLAGS_DEBUG
        VCPKG_C_FLAGS_RELEASE VCPKG_CXX_FLAGS_RELEASE
        VCPKG_LINKER_FLAGS VCPKG_LINKER_FLAGS_RELEASE VCPKG_LINKER_FLAGS_DEBUG
    )

    set(CMAKE_SYSTEM_NAME Linux CACHE STRING "")

    # Set compiler to clang
    set(CMAKE_C_COMPILER clang)
    set(CMAKE_CXX_COMPILER clang++)
    SET(CMAKE_ASM_COMPILER clang)

    # Pick target architecture for clang
    # VCPKG_TARGET_ARCHITECTURE is only defined while vcpkg builds a port. For
    # the project itself fall back to the preset's triplet; otherwise
    # CMAKE_SYSTEM_PROCESSOR stays empty and every x86_64-specific setting
    # (-mcmodel=large for the recompiled executable, -msse4.1) is skipped.
    set(_linux_clang_arch "${VCPKG_TARGET_ARCHITECTURE}")
    if(NOT _linux_clang_arch AND VCPKG_TARGET_TRIPLET MATCHES "^([^-]+)-")
        set(_linux_clang_arch "${CMAKE_MATCH_1}")
    endif()
    if(_linux_clang_arch STREQUAL "x64")
        set(CMAKE_SYSTEM_PROCESSOR x86_64 CACHE STRING "")
        set(CLANG_TARGET x86_64-unknown-linux-gnu)
    elseif(_linux_clang_arch STREQUAL "x86")
        set(CMAKE_SYSTEM_PROCESSOR i686 CACHE STRING "")
        set(CLANG_TARGET i686-unknown-linux-gnu)
    elseif(_linux_clang_arch STREQUAL "arm")
        set(CMAKE_SYSTEM_PROCESSOR armv7l CACHE STRING "")
        set(CLANG_TARGET armv7-unknown-linux-gnueabihf)
    elseif(_linux_clang_arch STREQUAL "arm64")
        set(CMAKE_SYSTEM_PROCESSOR aarch64 CACHE STRING "")
        set(CLANG_TARGET aarch64-unknown-linux-gnu)
    endif()
    if(DEFINED CLANG_TARGET)
        set(CMAKE_C_COMPILER_TARGET ${CLANG_TARGET})
        set(CMAKE_CXX_COMPILER_TARGET ${CLANG_TARGET})
        set(CMAKE_ASM_COMPILER_TARGET ${CLANG_TARGET})
    endif()

    if(CMAKE_HOST_SYSTEM_NAME STREQUAL "Linux" AND CMAKE_SYSTEM_PROCESSOR STREQUAL CMAKE_HOST_SYSTEM_PROCESSOR)
        set(CMAKE_CROSSCOMPILING OFF CACHE BOOL "")
    endif()

    string(APPEND CMAKE_C_FLAGS_INIT " -fPIC ${VCPKG_C_FLAGS} ")
    string(APPEND CMAKE_CXX_FLAGS_INIT " -fPIC ${VCPKG_CXX_FLAGS} ")
    string(APPEND CMAKE_C_FLAGS_DEBUG_INIT " ${VCPKG_C_FLAGS_DEBUG} ")
    string(APPEND CMAKE_CXX_FLAGS_DEBUG_INIT " ${VCPKG_CXX_FLAGS_DEBUG} ")
    string(APPEND CMAKE_C_FLAGS_RELEASE_INIT " ${VCPKG_C_FLAGS_RELEASE} ")
    string(APPEND CMAKE_CXX_FLAGS_RELEASE_INIT " ${VCPKG_CXX_FLAGS_RELEASE} ")

    # Use LLVM's lld linker
    set(CMAKE_LINKER_TYPE LLD)

    string(APPEND CMAKE_MODULE_LINKER_FLAGS_INIT " ${VCPKG_LINKER_FLAGS} ")
    string(APPEND CMAKE_SHARED_LINKER_FLAGS_INIT " ${VCPKG_LINKER_FLAGS} ")
    string(APPEND CMAKE_EXE_LINKER_FLAGS_INIT " ${VCPKG_LINKER_FLAGS} ")
    if(VCPKG_CRT_LINKAGE STREQUAL "static")
        string(APPEND CMAKE_MODULE_LINKER_FLAGS_INIT "-static ")
        string(APPEND CMAKE_SHARED_LINKER_FLAGS_INIT "-static ")
        string(APPEND CMAKE_EXE_LINKER_FLAGS_INIT "-static ")
    endif()
    string(APPEND CMAKE_MODULE_LINKER_FLAGS_DEBUG_INIT " ${VCPKG_LINKER_FLAGS_DEBUG} ")
    string(APPEND CMAKE_SHARED_LINKER_FLAGS_DEBUG_INIT " ${VCPKG_LINKER_FLAGS_DEBUG} ")
    string(APPEND CMAKE_EXE_LINKER_FLAGS_DEBUG_INIT " ${VCPKG_LINKER_FLAGS_DEBUG} ")
    string(APPEND CMAKE_MODULE_LINKER_FLAGS_RELEASE_INIT " ${VCPKG_LINKER_FLAGS_RELEASE} ")
    string(APPEND CMAKE_SHARED_LINKER_FLAGS_RELEASE_INIT " ${VCPKG_LINKER_FLAGS_RELEASE} ")
    string(APPEND CMAKE_EXE_LINKER_FLAGS_RELEASE_INIT " ${VCPKG_LINKER_FLAGS_RELEASE} ")
    string(APPEND CMAKE_ASM_FLAGS_INIT " ${VCPKG_C_FLAGS} ")
endif()
