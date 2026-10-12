cmake_minimum_required(VERSION 3.20)

project(callofrecomp LANGUAGES C CXX)

add_library(codrecomp_abi INTERFACE)
target_include_directories(codrecomp_abi INTERFACE
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
)

# Portable virtual filesystem and PK3 (ZIP store / raw DEFLATE) reader.
# Android NDK provides libz; keep the core independent of proprietary game files.
# Falls back to a pinned static zlib when the host has none (e.g. bare Windows).
find_package(ZLIB QUIET)
if(NOT ZLIB_FOUND)
    include(FetchContent)
    set(ZLIB_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
    FetchContent_Declare(zlib
        URL https://github.com/madler/zlib/releases/download/v1.3.1/zlib-1.3.1.tar.gz
        URL_HASH SHA256=9a93b2b7dfdac77ceba5a558a580e74667dd6fede4585b91eefb60f03b72df23
        EXCLUDE_FROM_ALL)
    FetchContent_MakeAvailable(zlib)
    target_include_directories(zlibstatic PUBLIC ${zlib_SOURCE_DIR} ${zlib_BINARY_DIR})
    add_library(ZLIB::ZLIB ALIAS zlibstatic)
endif()
add_library(codrecomp_vfs STATIC src/vfs.cpp)
target_link_libraries(codrecomp_vfs PUBLIC ZLIB::ZLIB)
target_link_libraries(codrecomp_vfs PUBLIC codrecomp_abi)
target_compile_features(codrecomp_vfs PUBLIC cxx_std_17)

# Host-services reader with explicit accepted mode and opaque native handles.
# This is a new host interface, not the original 32-bit x86 VM-word bridge.
add_library(codrecomp_read_only_host STATIC src/read_only_host_adapter.cpp)
target_link_libraries(codrecomp_read_only_host PUBLIC codrecomp_vfs)
target_compile_features(codrecomp_read_only_host PUBLIC cxx_std_17)

# Explicit guest-memory map and legacy read-only syscall bridge. Host memory
# stays native width even when the guest address format is 32-bit.
add_library(codrecomp_legacy_vm_fs STATIC
    src/guest_memory.cpp
    src/legacy_fs_read_bridge.cpp
)
target_link_libraries(codrecomp_legacy_vm_fs PUBLIC codrecomp_read_only_host)
target_compile_features(codrecomp_legacy_vm_fs PUBLIC cxx_std_17)

# Model a confirmed 55-byte SP engine searchpath insertion routine.
# Independent of actual VFS mount selection until the remaining flags are traced.
add_library(codrecomp_searchpath_order STATIC src/searchpath_order.cpp)
target_link_libraries(codrecomp_searchpath_order PUBLIC codrecomp_abi)
target_compile_features(codrecomp_searchpath_order PUBLIC cxx_std_17)

option(CODRECOMP_BUILD_TESTS "Build host-side reconstruction tests" ON)

if(CODRECOMP_BUILD_TESTS)
    enable_testing()

    add_executable(codrecomp_abi_smoke
        tests/abi_smoke.c
    )
    target_link_libraries(codrecomp_abi_smoke PRIVATE codrecomp_abi)
    set_target_properties(codrecomp_abi_smoke PROPERTIES
        C_STANDARD 11
        C_STANDARD_REQUIRED YES
        C_EXTENSIONS NO
    )

    add_test(NAME abi_smoke COMMAND codrecomp_abi_smoke)

    add_executable(codrecomp_host_services_smoke
        tests/host_services_smoke.c
    )
    target_link_libraries(codrecomp_host_services_smoke PRIVATE codrecomp_abi)
    set_target_properties(codrecomp_host_services_smoke PROPERTIES
        C_STANDARD 11
        C_STANDARD_REQUIRED YES
        C_EXTENSIONS NO
    )
    add_test(NAME host_services_smoke COMMAND codrecomp_host_services_smoke)

    add_executable(codrecomp_vfs_smoke tests/vfs_smoke.cpp)
    target_link_libraries(codrecomp_vfs_smoke PRIVATE codrecomp_vfs)
    add_test(NAME vfs_smoke COMMAND codrecomp_vfs_smoke)

    add_executable(codrecomp_host_adapter_smoke tests/host_adapter_smoke.cpp)
    target_link_libraries(codrecomp_host_adapter_smoke PRIVATE codrecomp_read_only_host)
    add_test(NAME host_adapter_smoke COMMAND codrecomp_host_adapter_smoke)

    add_executable(codrecomp_guest_vm_bridge_smoke tests/guest_vm_bridge_smoke.cpp)
    target_link_libraries(codrecomp_guest_vm_bridge_smoke PRIVATE codrecomp_legacy_vm_fs)
    add_test(NAME guest_vm_bridge_smoke COMMAND codrecomp_guest_vm_bridge_smoke)

    add_executable(codrecomp_searchpath_order_smoke tests/searchpath_order_smoke.cpp)
    target_link_libraries(codrecomp_searchpath_order_smoke PRIVATE codrecomp_searchpath_order)
    add_test(NAME searchpath_order_smoke COMMAND codrecomp_searchpath_order_smoke)

    add_executable(codrecomp_searchpath_locale_filter_smoke tests/searchpath_locale_filter_smoke.cpp)
    target_link_libraries(codrecomp_searchpath_locale_filter_smoke PRIVATE codrecomp_searchpath_order)
    add_test(NAME searchpath_locale_filter_smoke COMMAND codrecomp_searchpath_locale_filter_smoke)

    # Offline unit tests cover the PE parser and VM probe using synthetic
    # fixtures. CI already invokes CTest, so no workflow edit is required.
    find_package(Python3 COMPONENTS Interpreter QUIET)
    if(Python3_Interpreter_FOUND)
        add_test(
            NAME static_analysis_python
            COMMAND ${Python3_EXECUTABLE} -m unittest discover
                -s ${CMAKE_CURRENT_SOURCE_DIR}/tests
                -p "test_*.py"
                -v
        )
    endif()

    # Experimental p-code runtime requires compiler support for 128-bit integers.
    # These fixtures use synthetic inputs and do not require proprietary binaries.
    include(CheckCSourceCompiles)
    check_c_source_compiles("int main(void) { unsigned __int128 x = 1; return (int)(x - 1); }"
        CODRECOMP_HAS_INT128)
    if(CODRECOMP_HAS_INT128 AND Python3_Interpreter_FOUND)
        add_library(codrecomp_pcode_runtime STATIC
            tools/recomp/runtime/guest.c tools/recomp/runtime/kernel32.c
            tools/recomp/runtime/files.c)
        target_include_directories(codrecomp_pcode_runtime PUBLIC tools/recomp)
        if(NOT WIN32)
            target_link_libraries(codrecomp_pcode_runtime PUBLIC m)
        endif()
        add_executable(codrecomp_recomp_files_smoke tests/recomp_files_smoke.c)
        target_link_libraries(codrecomp_recomp_files_smoke PRIVATE codrecomp_pcode_runtime)
        add_test(NAME recomp_files_smoke COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/run_recomp_files_smoke.py
            $<TARGET_FILE:codrecomp_recomp_files_smoke>)

        find_package(SDL2 CONFIG QUIET)
        if(SDL2_FOUND)
            add_executable(codrecomp_recomp_gl_strings_smoke
                tests/recomp_gl_strings_smoke.c tools/recomp/runtime/window.c
                tools/recomp/runtime/gl_thunks.c)
            target_compile_definitions(codrecomp_recomp_gl_strings_smoke PRIVATE SDL_MAIN_HANDLED)
            target_include_directories(codrecomp_recomp_gl_strings_smoke PRIVATE tools/recomp/runtime)
            target_link_libraries(codrecomp_recomp_gl_strings_smoke PRIVATE
                codrecomp_pcode_runtime SDL2::SDL2)
            if(WIN32)
                add_custom_command(TARGET codrecomp_recomp_gl_strings_smoke POST_BUILD
                    COMMAND ${CMAKE_COMMAND} -E copy_if_different
                    $<TARGET_FILE:SDL2::SDL2> $<TARGET_FILE_DIR:codrecomp_recomp_gl_strings_smoke>)
            endif()
            add_test(NAME recomp_gl_strings_smoke COMMAND codrecomp_recomp_gl_strings_smoke)
        endif()
    endif()
endif()
