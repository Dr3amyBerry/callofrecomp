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

    # LLVM-MinGW C++ executables need their toolchain DLLs beside the tests.
    # Do not depend on the developer's PATH to locate libc++/libunwind.
    if(WIN32 AND MINGW)
        get_filename_component(cxx_bin "${CMAKE_CXX_COMPILER}" DIRECTORY)
        set(cxx_runtime_dlls)
        foreach(runtime_name libc++.dll libunwind.dll libwinpthread-1.dll)
            if(EXISTS "${cxx_bin}/${runtime_name}")
                list(APPEND cxx_runtime_dlls "${cxx_bin}/${runtime_name}")
            endif()
        endforeach()
        if(cxx_runtime_dlls)
            set(cxx_runtime_dir "${CMAKE_CURRENT_BINARY_DIR}")
            if(CMAKE_CONFIGURATION_TYPES)
                string(APPEND cxx_runtime_dir "/$<CONFIG>")
            endif()
            add_custom_target(codrecomp_test_runtime
                COMMAND ${CMAKE_COMMAND} -E make_directory "${cxx_runtime_dir}"
                COMMAND ${CMAKE_COMMAND} -E copy_if_different ${cxx_runtime_dlls} "${cxx_runtime_dir}"
                VERBATIM)
            foreach(cpp_test codrecomp_vfs_smoke codrecomp_host_adapter_smoke
                    codrecomp_guest_vm_bridge_smoke codrecomp_searchpath_order_smoke
                    codrecomp_searchpath_locale_filter_smoke)
                add_dependencies(${cpp_test} codrecomp_test_runtime)
            endforeach()
        endif()
    endif()

    add_executable(codrecomp_pe_loader_bounds_smoke tests/pe_loader_bounds_smoke.c)
    target_include_directories(codrecomp_pe_loader_bounds_smoke PRIVATE tools/recomp/runtime)
    add_test(NAME pe_loader_bounds_smoke COMMAND codrecomp_pe_loader_bounds_smoke)

    add_executable(codrecomp_frame_pacing_smoke tests/frame_pacing_smoke.c)
    target_include_directories(codrecomp_frame_pacing_smoke PRIVATE tools/recomp/runtime)
    add_test(NAME frame_pacing_smoke COMMAND codrecomp_frame_pacing_smoke)
    add_executable(codrecomp_loading_status_smoke tests/loading_status_smoke.c)
    target_include_directories(codrecomp_loading_status_smoke PRIVATE tools/recomp/runtime)
    add_test(NAME loading_status_smoke COMMAND codrecomp_loading_status_smoke)
    add_executable(codrecomp_commit_runs_smoke tests/commit_runs_smoke.c)
    target_include_directories(codrecomp_commit_runs_smoke PRIVATE tools/recomp/runtime)
    add_test(NAME commit_runs_smoke COMMAND codrecomp_commit_runs_smoke)
    add_executable(codrecomp_file_copy_smoke tests/file_copy_smoke.c)
    target_include_directories(codrecomp_file_copy_smoke PRIVATE tools/recomp/runtime)
    add_test(NAME file_copy_smoke COMMAND codrecomp_file_copy_smoke)
    add_executable(codrecomp_gl_lookup_smoke tests/gl_lookup_smoke.c)
    target_include_directories(codrecomp_gl_lookup_smoke PRIVATE tools/recomp tools/recomp/runtime)
    add_test(NAME gl_lookup_smoke COMMAND codrecomp_gl_lookup_smoke)
    add_executable(codrecomp_gl_time_smoke tests/gl_call_timing_smoke.c)
    target_include_directories(codrecomp_gl_time_smoke PRIVATE tools/recomp/runtime)
    add_test(NAME gl_call_timing_smoke COMMAND codrecomp_gl_time_smoke)
    add_executable(codrecomp_gl_vk_state_smoke
        tests/gl_vk_state_smoke.c
        tools/recomp/runtime/gl_vk_state.c)
    target_include_directories(codrecomp_gl_vk_state_smoke PRIVATE tools/recomp/runtime)
    if(NOT WIN32)
        target_link_libraries(codrecomp_gl_vk_state_smoke PRIVATE m)
    endif()
    add_test(NAME gl_vk_state_smoke COMMAND codrecomp_gl_vk_state_smoke)
    add_executable(codrecomp_gl_vk_matrix_transform_smoke
        tests/gl_vk_matrix_transform_smoke.c
        tools/recomp/runtime/gl_vk_state.c)
    target_include_directories(codrecomp_gl_vk_matrix_transform_smoke PRIVATE tools/recomp/runtime)
    if(NOT WIN32)
        target_link_libraries(codrecomp_gl_vk_matrix_transform_smoke PRIVATE m)
    endif()
    add_test(NAME gl_vk_matrix_transform_smoke COMMAND codrecomp_gl_vk_matrix_transform_smoke)

    add_executable(codrecomp_gl_perf_smoke tests/gl_perf_metrics_smoke.c)
    target_include_directories(codrecomp_gl_perf_smoke PRIVATE tools/recomp/runtime)
    add_test(NAME gl_perf_smoke COMMAND codrecomp_gl_perf_smoke)
    add_executable(codrecomp_x87_nan_bits_smoke tests/x87_nan_bits_smoke.c)
    target_include_directories(codrecomp_x87_nan_bits_smoke PRIVATE tools/recomp tools/recomp/runtime)
    if(NOT WIN32)
        target_link_libraries(codrecomp_x87_nan_bits_smoke PRIVATE m)
    endif()
    add_test(NAME x87_nan_bits_smoke COMMAND codrecomp_x87_nan_bits_smoke)

    add_executable(codrecomp_x87_normal_f2d_smoke tests/x87_normal_f2d_smoke.c)
    target_include_directories(codrecomp_x87_normal_f2d_smoke PRIVATE tools/recomp)
    if(NOT WIN32)
        target_link_libraries(codrecomp_x87_normal_f2d_smoke PRIVATE m)
    endif()
    add_test(NAME x87_normal_f2d_smoke COMMAND codrecomp_x87_normal_f2d_smoke)
    # Offline-only mathematical audit of a DISCARDED packing transformation.
    # No production converter or Android build flag is modified.
    add_executable(codrecomp_x87_packed_math_smoke tests/x87_packed_math_smoke.c)
    target_include_directories(codrecomp_x87_packed_math_smoke PRIVATE tools/recomp)
    if(NOT WIN32)
        target_link_libraries(codrecomp_x87_packed_math_smoke PRIVATE m)
    endif()
    add_test(NAME x87_packed_math_smoke COMMAND codrecomp_x87_packed_math_smoke)
    add_executable(codrecomp_fcom_smoke tests/codsp_fcom_smoke.c)
    target_include_directories(codrecomp_fcom_smoke PRIVATE tools/recomp tools/recomp/runtime)
    if(NOT WIN32)
        target_link_libraries(codrecomp_fcom_smoke PRIVATE m)
    endif()
    add_test(NAME codsp_fcom_smoke COMMAND codrecomp_fcom_smoke)
    add_executable(codrecomp_copy32_smoke tests/codsp_copy32_smoke.c)
    foreach(profile normal wsa)
        add_executable(codrecomp_launch_${profile}_smoke tests/launch_profile_smoke.c)
        target_include_directories(codrecomp_launch_${profile}_smoke PRIVATE tools/recomp/runtime)
        if(profile STREQUAL "wsa")
            target_compile_definitions(codrecomp_launch_${profile}_smoke PRIVATE CODRECOMP_WSA_RELEASE_DEFAULTS)
        endif()
        add_test(NAME launch_${profile}_smoke COMMAND codrecomp_launch_${profile}_smoke)
    endforeach()
    target_include_directories(codrecomp_copy32_smoke PRIVATE tools/recomp/runtime)
    add_test(NAME codsp_copy32_smoke COMMAND codrecomp_copy32_smoke)

    add_executable(codrecomp_compass_markers_smoke tests/compass_markers_smoke.c)
    target_include_directories(codrecomp_compass_markers_smoke PRIVATE tools/recomp/runtime)
    if(NOT WIN32)
        target_link_libraries(codrecomp_compass_markers_smoke PRIVATE m)
    endif()
    add_test(NAME compass_markers_smoke COMMAND codrecomp_compass_markers_smoke)

    add_executable(codrecomp_hot_x87_transform_smoke tests/hot_x87_transform_smoke.c)
    target_include_directories(codrecomp_hot_x87_transform_smoke PRIVATE tools/recomp/runtime)
    if(NOT WIN32)
        target_link_libraries(codrecomp_hot_x87_transform_smoke PRIVATE m)
    endif()
    add_test(NAME hot_x87_transform_smoke COMMAND codrecomp_hot_x87_transform_smoke)

    add_executable(codrecomp_profile_sampler_smoke tests/profile_sampler_smoke.c)
    target_include_directories(codrecomp_profile_sampler_smoke PRIVATE tools/recomp/runtime)
    add_test(NAME profile_sampler_smoke COMMAND codrecomp_profile_sampler_smoke)

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
    check_c_source_compiles("
        #if !defined(__x86_64__) || (!defined(__GNUC__) && !defined(__clang__))
        #error Native x87 lab requires GNU-style x86_64 assembly
        #endif
        int main(void) { __asm__ volatile(\"fnop\"); return 0; }"
        CODRECOMP_HAS_NATIVE_X87)
    if(CODRECOMP_HAS_NATIVE_X87)
        # Isolated binary80 primitive only; never enables a guest fast path.
        add_executable(codrecomp_x87_native_math_smoke tests/x87_native_math_smoke.c)
        target_include_directories(codrecomp_x87_native_math_smoke PRIVATE tools/recomp)
        add_test(NAME x87_native_math_smoke COMMAND codrecomp_x87_native_math_smoke)
        add_executable(codrecomp_x87_native_state_smoke tests/x87_native_state_smoke.c)
        target_include_directories(codrecomp_x87_native_state_smoke PRIVATE tools/recomp)
        add_test(NAME x87_native_state_smoke COMMAND codrecomp_x87_native_state_smoke)
        add_executable(codrecomp_native_x87_bridge_smoke tests/native_x87_bridge_smoke.c)
        target_include_directories(codrecomp_native_x87_bridge_smoke PRIVATE tools/recomp)
        add_test(NAME native_x87_bridge_smoke COMMAND codrecomp_native_x87_bridge_smoke)
    endif()
    check_c_source_compiles("int main(void) { unsigned __int128 x = 1; return (int)(x - 1); }"
        CODRECOMP_HAS_INT128)
    if(CODRECOMP_HAS_INT128)
        # Synthetic x87 binary80 stack copy equivalence experiment.
        # This is NOT enabled in the Android game runtime.
        add_executable(codrecomp_x87_stack_copy_lab_smoke tests/x87_stack_copy_lab.c)
        add_test(NAME x87_stack_copy_lab_smoke COMMAND codrecomp_x87_stack_copy_lab_smoke)
        if(Python3_Interpreter_FOUND)
            set_tests_properties(static_analysis_python PROPERTIES
                ENVIRONMENT "RECOMP_TEST_CC=${CMAKE_C_COMPILER}")
        endif()
        add_executable(codrecomp_overflow_flags_smoke tests/overflow_flags_smoke.c)
        target_include_directories(codrecomp_overflow_flags_smoke PRIVATE tools/recomp)
        add_test(NAME overflow_flags_smoke COMMAND codrecomp_overflow_flags_smoke)
        add_executable(codrecomp_recomp_x87_smoke tests/recomp_x87_smoke.c)
        target_include_directories(codrecomp_recomp_x87_smoke PRIVATE tools/recomp)
        if(NOT WIN32)
            target_link_libraries(codrecomp_recomp_x87_smoke PRIVATE m)
        endif()
        add_test(NAME recomp_x87_smoke COMMAND codrecomp_recomp_x87_smoke)
    endif()
    if(CODRECOMP_HAS_INT128 AND Python3_Interpreter_FOUND)
        add_library(codrecomp_pcode_runtime STATIC
            tools/recomp/runtime/guest.c tools/recomp/runtime/kernel32.c
            tools/recomp/runtime/files.c)
        target_include_directories(codrecomp_pcode_runtime PUBLIC tools/recomp)
        add_executable(codrecomp_dispatch_index_smoke tests/dispatch_index_smoke.c)
        target_include_directories(codrecomp_dispatch_index_smoke PRIVATE tools/recomp tools/recomp/runtime)
        add_test(NAME dispatch_index_smoke COMMAND codrecomp_dispatch_index_smoke)
        # Manual only: synthetic lookup CPU benchmark. Never interpret it as
        # Call of Duty gameplay FPS or an ARM64 speedup.
        add_executable(codrecomp_dispatch_recent_bench tests/dispatch_recent_bench.c)
        target_include_directories(codrecomp_dispatch_recent_bench PRIVATE
            tools/recomp tools/recomp/runtime)
        if(NOT WIN32)
            target_link_libraries(codrecomp_pcode_runtime PUBLIC m)
        endif()
        add_executable(codrecomp_recomp_files_smoke tests/recomp_files_smoke.c)
        target_link_libraries(codrecomp_recomp_files_smoke PRIVATE codrecomp_pcode_runtime)
        add_executable(codrecomp_recomp_memory_smoke tests/recomp_memory_smoke.c)
        target_link_libraries(codrecomp_recomp_memory_smoke PRIVATE codrecomp_pcode_runtime)
        add_executable(codrecomp_recomp_module_lifecycle_smoke tests/recomp_module_lifecycle_smoke.c)
        target_link_libraries(codrecomp_recomp_module_lifecycle_smoke PRIVATE codrecomp_pcode_runtime)
        add_test(NAME recomp_module_lifecycle_smoke COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/run_recomp_module_lifecycle_smoke.py
            $<TARGET_FILE:codrecomp_recomp_module_lifecycle_smoke>)
        add_test(NAME recomp_memory_smoke COMMAND codrecomp_recomp_memory_smoke)
        add_test(NAME recomp_files_smoke COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/run_recomp_files_smoke.py
            $<TARGET_FILE:codrecomp_recomp_files_smoke>)

        find_package(SDL2 CONFIG QUIET)
        if(SDL2_FOUND)
            add_executable(codrecomp_recomp_audio_smoke
                tests/recomp_audio_smoke.c tools/recomp/runtime/audio.c)
            target_compile_definitions(codrecomp_recomp_audio_smoke PRIVATE SDL_MAIN_HANDLED)
            target_include_directories(codrecomp_recomp_audio_smoke PRIVATE tools/recomp/runtime)
            target_link_libraries(codrecomp_recomp_audio_smoke PRIVATE codrecomp_pcode_runtime SDL2::SDL2)
            add_executable(codrecomp_recomp_gl_strings_smoke
                tests/recomp_gl_strings_smoke.c tools/recomp/runtime/window.c
                tools/recomp/runtime/gl_thunks.c)
            target_compile_definitions(codrecomp_recomp_gl_strings_smoke PRIVATE SDL_MAIN_HANDLED)
            target_include_directories(codrecomp_recomp_gl_strings_smoke PRIVATE tools/recomp/runtime)
            target_link_libraries(codrecomp_recomp_gl_strings_smoke PRIVATE
                codrecomp_pcode_runtime SDL2::SDL2)
            if(WIN32)
                foreach(sdl_test codrecomp_recomp_gl_strings_smoke codrecomp_recomp_audio_smoke)
                add_custom_command(TARGET ${sdl_test} POST_BUILD
                    COMMAND ${CMAKE_COMMAND} -E copy_if_different
                    $<TARGET_FILE:SDL2::SDL2> $<TARGET_FILE_DIR:${sdl_test}>)
                endforeach()
            endif()
            add_test(NAME recomp_gl_strings_smoke COMMAND codrecomp_recomp_gl_strings_smoke)
            add_test(NAME recomp_audio_smoke COMMAND codrecomp_recomp_audio_smoke)
        endif()
    endif()
endif()
