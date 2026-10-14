cmake_minimum_required(VERSION 3.22)
project(callofrecomp_android C)
if(NOT ANDROID)
  message(FATAL_ERROR "Configure with the Android NDK toolchain")
endif()
set(CMAKE_C_STANDARD 11)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(SDL_SHARED ON CACHE BOOL "" FORCE)
set(SDL_STATIC OFF CACHE BOOL "" FORCE)
set(SDL_TEST OFF CACHE BOOL "" FORCE)
add_subdirectory("${SDL2_SOURCE_DIR}" sdl)
foreach(option ANDROID NOX11 NOEGL NO_LOADER NO_INIT_CONSTRUCTOR USE_ANDROID_LOG)
  set(${option} ON CACHE BOOL "" FORCE)
endforeach()
set(STATICLIB OFF CACHE BOOL "" FORCE)
add_subdirectory("${GL4ES_SOURCE_DIR}" gl4es)
set(ROOT "${CMAKE_CURRENT_SOURCE_DIR}/..")
set(RECOMP_SOURCE_DIR "${ROOT}/recomp_out" CACHE PATH "Private generated C")
file(GLOB RUNTIME "${ROOT}/tools/recomp/runtime/*.c")
set(GENERATED)
foreach(module codsp uix86 cgamex86 gamex86)
  file(GLOB sources "${RECOMP_SOURCE_DIR}/${module}_recomp*.c")
  if(NOT sources)
    message(FATAL_ERROR "Missing private generated ${module} sources")
  endif()
  list(APPEND GENERATED ${sources})
endforeach()
add_library(main SHARED native_host.c ${RUNTIME} ${GENERATED})
set(RECOMP_OPTIMIZATION "1" CACHE STRING "Generated-code optimization (0 or 1)")
# Hundreds of thousands of short-lived generated arrays do not need variable
# debug records. Keep PC-to-source line information without enormous DWARF trees.
set_source_files_properties(${GENERATED} PROPERTIES COMPILE_OPTIONS "-gline-tables-only")
if(RECOMP_OPTIMIZATION STREQUAL "0")
  set_source_files_properties(${GENERATED} PROPERTIES COMPILE_OPTIONS "-O0")
endif()
target_include_directories(main PRIVATE "${ROOT}/tools/recomp" "${ROOT}/tools/recomp/runtime"
  "${SDL2_SOURCE_DIR}/include" "${GL4ES_SOURCE_DIR}/include")
target_compile_definitions(main PRIVATE SDL_MAIN_HANDLED)
option(CODRECOMP_CPU_PROFILING "Compile opt-in sampled CPU diagnostics" OFF)
if(CODRECOMP_CPU_PROFILING)
  # Only guest.c consumes this flag. Do not recompile all private generated
  # modules just to turn local diagnostics on or off.
  set_property(SOURCE "${ROOT}/tools/recomp/runtime/guest.c" APPEND
    PROPERTY COMPILE_DEFINITIONS CODRECOMP_CPU_PROFILING)
endif()
# Diagnostic only: compile both producer and frame boundary without rebuilding
# the large private generated C. The normal APK has no GL counter overhead.
option(CODRECOMP_GL_PROFILING "Compile opt-in guest GL call counters" OFF)
if(CODRECOMP_GL_PROFILING)
  foreach(source gl_thunks.c window.c)
    set_property(SOURCE "${ROOT}/tools/recomp/runtime/${source}" APPEND
      PROPERTY COMPILE_DEFINITIONS CODRECOMP_GL_PROFILING)
  endforeach()
endif()
# Opt-in CPU time attributable to GL4ES/GLES entry points on the guest thread.
# The normal build never pays the clock_gettime cost.
option(CODRECOMP_GL_TIMING "Compile opt-in renderer GL call CPU timing" OFF)
if(CODRECOMP_GL_TIMING)
  foreach(source gl_thunks.c window.c)
    set_property(SOURCE "${ROOT}/tools/recomp/runtime/${source}" APPEND
      PROPERTY COMPILE_DEFINITIONS CODRECOMP_GL_TIMING)
  endforeach()
endif()
# Experimental selectively higher optimization for *only* the two generated
# CoDSP translation units containing the hottest sampled renderer chunks.
# Default remains -O1 for the game and other generated modules.
option(CODRECOMP_RENDER_O2 "Use -O2 for CoDSP renderer partitions p10/p11 only" OFF)
if(CODRECOMP_RENDER_O2)
  foreach(part p10 p11)
    set(renderer_part "${RECOMP_SOURCE_DIR}/codsp_recomp_${part}.c")
    if(EXISTS "${renderer_part}")
      set_property(SOURCE "${renderer_part}" APPEND PROPERTY COMPILE_OPTIONS "-O2")
    else()
      message(FATAL_ERROR "Required experimental CoDSP source missing: ${renderer_part}")
    endif()
  endforeach()
endif()
# Opt-in ARM64 experiment, disabled in normal APKs. Only guest.c changes.
option(CODRECOMP_HOT_X87_FASTPATH "Use validated CoDSP 1.5 transform fast path" OFF)
if(CODRECOMP_HOT_X87_FASTPATH)
  set_property(SOURCE "${ROOT}/tools/recomp/runtime/guest.c" APPEND PROPERTY
    COMPILE_DEFINITIONS CODRECOMP_HOT_X87_FASTPATH)
  set_property(SOURCE "${ROOT}/tools/recomp/runtime/guest.c" APPEND PROPERTY
    COMPILE_OPTIONS "-ffp-contract=off")
endif()
# Opt-in targeted compiler experiment for the original 1.5 0x004Dxxxx
# frustum/visibility traversal group. All four hottest visibility functions
# reside in CoDSP generated partition p8. Preserve strict FP expression
# ordering while testing the compiler optimizer; no global -O2 or fast-math.
option(CODRECOMP_VISIBILITY_O2 "Use -O2 for CoDSP visibility partition p8 only" OFF)
if(CODRECOMP_VISIBILITY_O2)
  set(visibility_part "${RECOMP_SOURCE_DIR}/codsp_recomp_p8.c")
  if(NOT EXISTS "${visibility_part}")
    message(FATAL_ERROR "Required experimental CoDSP visibility part p8 missing")
  endif()
  set_property(SOURCE "${visibility_part}" APPEND PROPERTY COMPILE_OPTIONS
    "-O2;-ffp-contract=off")
endif()
# Opt-in CoDSP 1.5 32-byte MOV-loop specialization. The default build
# follows the original generated MOV instructions unchanged; only the
# ignored CoDSP generated p1 translation unit sees the compile definition.
option(CODRECOMP_CODSP_COPY32_FASTPATH "Experimental CoDSP 1.5 guarded copy32 loop" OFF)
if(CODRECOMP_CODSP_COPY32_FASTPATH)
  set(copy_part "${RECOMP_SOURCE_DIR}/codsp_recomp_p1.c")
  if(NOT EXISTS "${copy_part}")
    message(FATAL_ERROR "Required private CoDSP p1 copy source missing")
  endif()
  set_property(SOURCE "${copy_part}" APPEND PROPERTY
    COMPILE_DEFINITIONS CODRECOMP_CODSP_COPY32_FASTPATH)
endif()
# Native bit classification for x87 FLOAT_NAN in the original CoDSP 1.5
# geometry/visibility hot partitions. Works only after private source
# validation/injection (build_android.py --x87-nan-bits). No guest arithmetic,
# x87 control word or normal-build behavior is changed.
option(CODRECOMP_X87_NAN_BITS "Experimental exact binary80 NaN bit classification on p1/p8" OFF)
if(CODRECOMP_X87_NAN_BITS)
  foreach(part p1 p8)
    set(nan_part "${RECOMP_SOURCE_DIR}/codsp_recomp_${part}.c")
    if(NOT EXISTS "${nan_part}")
      message(FATAL_ERROR "Missing CoDSP source for binary80 NaN experiment: ${nan_part}")
    endif()
    file(STRINGS "${nan_part}" nan_include REGEX "^#include .x87_nan_bits.h.$")
    if(NOT nan_include)
      message(FATAL_ERROR "Private CoDSP source lacks validated binary80 NaN patch: ${nan_part}")
    endif()
    set_property(SOURCE "${nan_part}" APPEND PROPERTY
      COMPILE_DEFINITIONS CODRECOMP_X87_NAN_BITS)
  endforeach()
endif()
# Selectively accelerate exactly representable x87 normal->double on
# CoDSP geometry/visibility p1 and p8; no generated source rewriting.
# The original bit-equivalent f2d is preserved for all other encodings.
option(CODRECOMP_X87_NORMAL_F2D "Experimental canonical binary80-to-double fast path for CoDSP p1/p8" OFF)
if(CODRECOMP_X87_NORMAL_F2D)
  foreach(part p1 p8)
    set(float_part "${RECOMP_SOURCE_DIR}/codsp_recomp_${part}.c")
    if(NOT EXISTS "${float_part}")
      message(FATAL_ERROR "Missing private CoDSP p1/p8 for x87 f2d experiment")
    endif()
    set_property(SOURCE "${float_part}" APPEND PROPERTY
      COMPILE_DEFINITIONS CODRECOMP_X87_NORMAL_F2D)
  endforeach()
endif()
target_compile_options(main PRIVATE -O1 -Wno-unused-function)
target_link_libraries(main PRIVATE SDL2 GL log android m dl)
target_link_libraries(GL m dl)
foreach(target SDL2 GL main)
  set_target_properties(${target} PROPERTIES LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib"
    SUFFIX ".so")
  target_link_options(${target} PRIVATE "-Wl,-z,max-page-size=16384")
endforeach()
