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
# Pure opt-in observer implementation; do not link it into the normal APK.
list(REMOVE_ITEM RUNTIME "${ROOT}/tools/recomp/runtime/gl_vk_state.c")
list(REMOVE_ITEM RUNTIME "${ROOT}/tools/recomp/runtime/native_x87_bridge.c")
set(GENERATED)
foreach(module codsp uix86 cgamex86 gamex86)
  file(GLOB sources "${RECOMP_SOURCE_DIR}/${module}_recomp*.c")
  if(NOT sources)
    message(FATAL_ERROR "Missing private generated ${module} sources")
  endif()
  list(APPEND GENERATED ${sources})
endforeach()
add_library(main SHARED native_host.c ${RUNTIME} ${GENERATED})
option(CODRECOMP_LOCAL_GUEST_STATE "WSA experiment: bind guest data within libmain" OFF)
if(CODRECOMP_LOCAL_GUEST_STATE)
  if(NOT ANDROID_ABI STREQUAL "x86_64")
    message(FATAL_ERROR "Local guest state experiment requires WSA x86_64")
  endif()
  target_link_options(main PRIVATE "-Wl,--version-script=${CMAKE_CURRENT_SOURCE_DIR}/guest_state.map")
  set_property(TARGET main APPEND PROPERTY LINK_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/guest_state.map")
endif()
option(CODRECOMP_NATIVE_X87_REGION "Experimental original binary80 WSA region" OFF)
if(CODRECOMP_NATIVE_X87_REGION)
  if(NOT ANDROID_ABI STREQUAL "x86_64")
    message(FATAL_ERROR "Native x87 requires x86_64")
  endif()
  set(region "${RECOMP_SOURCE_DIR}/codsp_native_x87_region.c")
  file(READ "${RECOMP_SOURCE_DIR}/codsp_native_x87_region.json" manifest)
  string(JSON expected GET "${manifest}" source_sha256)
  file(SHA256 "${region}" actual)
  if(NOT actual STREQUAL expected)
    message(FATAL_ERROR "Native x87 source hash mismatch")
  endif()
  target_sources(main PRIVATE "${region}" "${ROOT}/tools/recomp/runtime/native_x87_bridge.c")
  set_source_files_properties("${region}" PROPERTIES COMPILE_OPTIONS "-O2;-fno-lto")
  foreach(source "${ROOT}/tools/recomp/runtime/guest.c" native_host.c)
    set_property(SOURCE "${source}" APPEND PROPERTY COMPILE_DEFINITIONS CODRECOMP_NATIVE_X87_REGION)
  endforeach()
endif()
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
# Dispatch last-hit cache is deliberately off in normal APKs until a
# game-level ARM64 A/B confirms it is faster than the existing page index.
option(CODRECOMP_DISPATCH_LAST_CACHE
  "Experiment: per-guest-run last-chunk hint with module-layout invalidation" OFF)
if(CODRECOMP_DISPATCH_LAST_CACHE)
  set_property(SOURCE "${ROOT}/tools/recomp/runtime/guest.c" APPEND
    PROPERTY COMPILE_DEFINITIONS CODRECOMP_DISPATCH_LAST_CACHE)
endif()
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
# Diagnostic ONLY: compare actual WSA gameplay with and without the fixed
# 60-FPS host cap. This does not switch renderer or improve GPU throughput.
option(CODRECOMP_WSA_UNCAP_BENCH "Disable 60-FPS cap only in WSA x86_64 diagnostic build" OFF)
if(CODRECOMP_WSA_UNCAP_BENCH)
  if(NOT ANDROID_ABI STREQUAL "x86_64")
    message(FATAL_ERROR "CODRECOMP_WSA_UNCAP_BENCH must only target WSA x86_64")
  endif()
  set_property(SOURCE "${ROOT}/tools/recomp/runtime/window.c" APPEND
    PROPERTY COMPILE_DEFINITIONS CODRECOMP_WSA_UNCAP_BENCH)
endif()

# Observation only. The GL4ES host call remains authoritative; Vulkan
# state recorder is OFF by default and only GL wrappers + swap frame compile
# with instrumentation. This is NOT a Vulkan rendering backend for the game.
option(CODRECOMP_GL_VK_STATE_CAPTURE "Opt-in typed legacy OpenGL state observer for Vulkan research" OFF)
if(CODRECOMP_GL_VK_STATE_CAPTURE)
  target_sources(main PRIVATE "${ROOT}/tools/recomp/runtime/gl_vk_state.c")
  foreach(source gl_thunks.c window.c)
    set_property(SOURCE "${ROOT}/tools/recomp/runtime/${source}" APPEND
      PROPERTY COMPILE_DEFINITIONS CODRECOMP_GL_VK_STATE_CAPTURE)
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
# Phase 13: whole-hot-chunk compilation, NOT operation-by-operation tuning.
# Covers historical TECNO hotspots in geometry p0/p1 and traversal p4.
# Visibility p8 is intentionally excluded after its ARM64 -O2 regression.
# This never changes guest assets, graphics quality or source semantics, but
# Clang code generation can still affect CPU timing. OFF without device A/B.
option(CODRECOMP_CORE_HOT_O2
  "EXPERIMENT: -O2 (strict FP) for physical-profiled CoDSP geometry/traversal p0/p1/p4 only" OFF)
if(CODRECOMP_CORE_HOT_O2)
  if(NOT ANDROID_ABI STREQUAL "arm64-v8a")
    message(FATAL_ERROR "CODRECOMP_CORE_HOT_O2 is ARM64-only")
  endif()
  if(NOT RECOMP_OPTIMIZATION STREQUAL "1")
    message(FATAL_ERROR "CODRECOMP_CORE_HOT_O2 requires RECOMP_OPTIMIZATION=1")
  endif()
  set(profile_pcode "${RECOMP_SOURCE_DIR}/codsp.pcode")
  if(NOT EXISTS "${profile_pcode}")
    message(FATAL_ERROR "Missing original CoDSP p-code for hot-chunk -O2")
  endif()
  file(SHA256 "${profile_pcode}" profile_pcode_hash)
  if(NOT profile_pcode_hash STREQUAL
      "36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e")
    message(FATAL_ERROR "Hot-chunk -O2 requires verified CoDSP.exe 1.5 p-code")
  endif()
  foreach(part p0 p1 p4)
    set(hot_source "${RECOMP_SOURCE_DIR}/codsp_recomp_${part}.c")
    if(NOT EXISTS "${hot_source}")
      message(FATAL_ERROR "Missing profiled CoDSP partition: ${hot_source}")
    endif()
    # Keep IEEE operation order and x87 results; no global -ffast-math,
    # no feature/geometry/visibility pruning or image-quality compromise.
    set_property(SOURCE "${hot_source}" APPEND PROPERTY
      COMPILE_OPTIONS "-O2;-ffp-contract=off")
  endforeach()
endif()

# Phase14C/D: original 29-instruction integer-only geometry CFG region.
# Default and fallback are the UNMODIFIED CoDSP p-code generated partitions.
# Only ARM64 experimental builds may link this privately generated helper.
# The helper is emitted after 40+ independent Unicorn-original x86 state
# comparisons: tools/recomp/diagnostics/emit_verified_cfg_region.py
# No C derived from a commercial game is added to public Git.
option(CODRECOMP_CFG14_GEOM_REGION
  "OFFLINE-VERIFIED EXPERIMENT: guarded CoDSP 1.5 0x0041C017 CFG region, OFF" OFF)
if(CODRECOMP_CFG14_GEOM_REGION)
  # Phase14D: independent Unicorn page-fault audit on real CoDSP 1.5 bytes
  # found 15/18 unsafe R/PC snapshots on mid-region memory exceptions.
  # Normal-exit 40/40 success does NOT make this eligible for runtime.
  # Fail closed for direct CMake callers too; cannot bypass via CLI.
  message(FATAL_ERROR
    "CFG14 FAULT_STATE_UNSAFE: 15/18 original x86 guest memory-fault "
    "boundaries leave cached R/PC stale; implement verified exception-safe "
    "deoptimization before enabling any APK build")
  if(NOT ANDROID_ABI STREQUAL "arm64-v8a")
    message(FATAL_ERROR "CFG14 CoDSP geometry experiment is ARM64 only")
  endif()
  if(NOT RECOMP_OPTIMIZATION STREQUAL "1")
    message(FATAL_ERROR "CFG14 CoDSP geometry requires RECOMP_OPTIMIZATION=1")
  endif()
  set(cfg14_pcode "${RECOMP_SOURCE_DIR}/codsp.pcode")
  set(cfg14_map "${RECOMP_SOURCE_DIR}/codsp_function_map_v2.json")
  set(cfg14_source "${RECOMP_SOURCE_DIR}/codsp_cfg14_geom_41c017.c")
  foreach(required_file IN ITEMS "${cfg14_pcode}" "${cfg14_map}" "${cfg14_source}")
    if(NOT EXISTS "${required_file}")
      message(FATAL_ERROR "CFG14 requires verified PRIVATE CoDSP file: ${required_file}")
    endif()
  endforeach()
  file(SHA256 "${cfg14_pcode}" cfg14_pcode_hash)
  file(SHA256 "${cfg14_map}" cfg14_map_hash)
  file(SHA256 "${cfg14_source}" cfg14_source_hash)
  if(NOT cfg14_pcode_hash STREQUAL
      "36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e")
    message(FATAL_ERROR "CFG14 p-code CoDSP 1.5 provenance mismatch")
  endif()
  if(NOT cfg14_map_hash STREQUAL
      "f6d56b4d167df2fb66a9f18ff8624e6b48fd363eadcbd05e62fa2598cd03ab4c")
    message(FATAL_ERROR "CFG14 original-body Ghidra B map provenance mismatch")
  endif()
  if(NOT cfg14_source_hash STREQUAL
      "dfd2655e497bbf8fa83ad434244f6a33d1afcccca5308bd413c523919cd19899")
    message(FATAL_ERROR "CFG14 generated private helper fingerprint mismatch; run the verified emitter")
  endif()
  target_sources(main PRIVATE "${cfg14_source}")
  set_property(SOURCE "${cfg14_source}" APPEND PROPERTY COMPILE_OPTIONS
    "-O1;-ffp-contract=off")
  set_property(SOURCE "${ROOT}/tools/recomp/runtime/guest.c" APPEND
    PROPERTY COMPILE_DEFINITIONS CODRECOMP_CFG14_GEOM_REGION)
endif()

# Legacy transform experiment: output-precision failure against original x86.
option(CODRECOMP_HOT_X87_FASTPATH "BLOCKED: legacy transform fails original x87 precision" OFF)
if(CODRECOMP_HOT_X87_FASTPATH)
  message(FATAL_ERROR "ORIGINAL_X87_PRECISION_UNSAFE: independent original-x86 cancellation outputs differ; do not enable the legacy double transform")
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
    file(STRINGS "${nan_part}" nan_include REGEX "^#include .(x87_nan_bits|codsp_fcom).h.$")
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
# Offline-only extension of the existing bit-exact x87 normal->double helper
# to p4, which contains CPU-sampled CoDSP traversal/state functions.
# Do NOT silently broaden the verified p1/p8 production-like experiment.
# Fail closed for unverified guest p-code and separate source variants.
option(CODRECOMP_X87_NORMAL_F2D_P4
  "EXPERIMENT: extend canonical x87 normal->double to CoDSP p4 (ARM64 unvalidated)" OFF)
if(CODRECOMP_X87_NORMAL_F2D_P4)
  if(NOT CODRECOMP_X87_NORMAL_F2D)
    message(FATAL_ERROR "p4 x87 conversion requires CODRECOMP_X87_NORMAL_F2D")
  endif()
  set(p4_source "${RECOMP_SOURCE_DIR}/codsp_recomp_p4.c")
  set(pcode_source "${RECOMP_SOURCE_DIR}/codsp.pcode")
  if(NOT EXISTS "${p4_source}" OR NOT EXISTS "${pcode_source}")
    message(FATAL_ERROR "Missing private verified CoDSP 1.5 p4 and p-code")
  endif()
  file(SHA256 "${pcode_source}" pcode_sha256)
  if(NOT pcode_sha256 STREQUAL
      "36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e")
    message(FATAL_ERROR "p4 x87 conversion requires verified CoDSP.exe 1.5 p-code")
  endif()
  # Check the generated C as well as the source p-code; otherwise a stale
  # or manually patched p4 could be compiled against an unrelated original.
  file(SHA256 "${p4_source}" p4_source_sha256)
  if(NOT p4_source_sha256 STREQUAL
      "ee9156183cc0410bf0641592f93d3d0efa4febc906cc014969ddb30d95a196d3")
    message(FATAL_ERROR "p4 x87 conversion requires verified original generated CoDSP p4")
  endif()
  # Keep the bit-exact converter INLINE; an out-of-line variant was rejected
  # after a NaN payload mismatch in a real p4 FLOAT_MULT differential oracle.
  set_property(SOURCE "${p4_source}" APPEND PROPERTY
    COMPILE_DEFINITIONS CODRECOMP_X87_NORMAL_F2D)
endif()
# Offline research only: restrict the same canonical checked x87 converter
# to verified guest-instruction labels within the four hottest p4 original
# function bodies. The private source patch explicitly #undef's the globally
# mapped f2d macro, preserving the old f2d for all other p4 instructions.
# This must not be combined with the prior whole-p4 experiment.
option(CODRECOMP_X87_NORMAL_F2D_P4_SELECTIVE
  "EXPERIMENT: checked x87 conversion at 520 original CoDSP p4 call sites" OFF)
if(CODRECOMP_X87_NORMAL_F2D_P4_SELECTIVE)
  if(NOT ANDROID_ABI STREQUAL "arm64-v8a")
    message(FATAL_ERROR "Selective p4 x87 conversion is ARM64-only")
  endif()
  if(NOT CODRECOMP_X87_NORMAL_F2D OR CODRECOMP_X87_NORMAL_F2D_P4)
    message(FATAL_ERROR "Selective p4 requires x87-normal-f2d and excludes whole-p4")
  endif()
  set(p4_source "${RECOMP_SOURCE_DIR}/codsp_recomp_p4.c")
  set(pcode_source "${RECOMP_SOURCE_DIR}/codsp.pcode")
  if(NOT EXISTS "${p4_source}" OR NOT EXISTS "${pcode_source}")
    message(FATAL_ERROR "Selective p4 requires private CoDSP C and p-code")
  endif()
  file(SHA256 "${pcode_source}" pcode_sha256)
  if(NOT pcode_sha256 STREQUAL
      "36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e")
    message(FATAL_ERROR "Selective p4 requires original CoDSP 1.5 p-code")
  endif()
  file(SHA256 "${p4_source}" p4_source_sha256)
  if(NOT p4_source_sha256 STREQUAL
      "b9a667ba9f467be99d94e3ca6ce6464b8a3e1ddfaf04c1ff17715beeb70fe284")
    message(FATAL_ERROR "Selective p4 requires verified exact label-local C patch")
  endif()
  set_property(SOURCE "${p4_source}" APPEND PROPERTY COMPILE_DEFINITIONS
    CODRECOMP_X87_NORMAL_F2D CODRECOMP_X87_NORMAL_F2D_P4_SELECTIVE)
endif()
# Two-session profile-guided refinement of the opt-in CoDSP p4 conversion:
# 124 original PCs with >=2 attributed x87 f2d samples, 277 static call
# sites. This is NOT validated Android gameplay performance.
option(CODRECOMP_X87_NORMAL_F2D_P4_PROFILED
  "EXPERIMENT: inline exact x87 conversion at 277 sampled p4 sites" OFF)
if(CODRECOMP_X87_NORMAL_F2D_P4_PROFILED)
  if(NOT ANDROID_ABI STREQUAL "arm64-v8a")
    message(FATAL_ERROR "Profiled p4 x87 conversion is ARM64-only")
  endif()
  if(NOT CODRECOMP_X87_NORMAL_F2D OR
     CODRECOMP_X87_NORMAL_F2D_P4 OR
     CODRECOMP_X87_NORMAL_F2D_P4_SELECTIVE)
    message(FATAL_ERROR
      "Profiled p4 requires base x87 converter; excludes full/selective p4")
  endif()
  set(p4_source "${RECOMP_SOURCE_DIR}/codsp_recomp_p4.c")
  set(pcode_source "${RECOMP_SOURCE_DIR}/codsp.pcode")
  if(NOT EXISTS "${p4_source}" OR NOT EXISTS "${pcode_source}")
    message(FATAL_ERROR "Profiled p4 requires private CoDSP 1.5 C and p-code")
  endif()
  file(SHA256 "${pcode_source}" pcode_sha256)
  if(NOT pcode_sha256 STREQUAL
      "36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e")
    message(FATAL_ERROR "Profiled p4 refuses unknown original CoDSP p-code")
  endif()
  file(SHA256 "${p4_source}" p4_source_sha256)
  if(NOT p4_source_sha256 STREQUAL
      "9b3d27670850fcdad26b7318374e7614102650e5d03825c4b28843e6be444b90")
    message(FATAL_ERROR "Profiled p4 refuses unverified generated guest C")
  endif()
  set_property(SOURCE "${p4_source}" APPEND PROPERTY COMPILE_DEFINITIONS
    CODRECOMP_X87_NORMAL_F2D CODRECOMP_X87_NORMAL_F2D_P4_PROFILED)
endif()
# CPU sample-guided, full-status and one-pop x87 compare optimization.
# Only source-verified CoDSP 1.5 p1/p8 p-code shapes; normal APK unchanged.
option(CODRECOMP_X87_FCOM_FASTPATH "Experimental full x87 FCOM+pop on verified CoDSP p1/p8 blocks" OFF)
if(CODRECOMP_X87_FCOM_FASTPATH)
  foreach(part p1 p8)
    set(fcom_part "${RECOMP_SOURCE_DIR}/codsp_recomp_${part}.c")
    if(NOT EXISTS "${fcom_part}")
      message(FATAL_ERROR "Missing CoDSP p1/p8 FCOM generated source")
    endif()
    file(STRINGS "${fcom_part}" fcom_include REGEX "^#include .codsp_fcom.h.$")
    if(NOT fcom_include)
      message(FATAL_ERROR "CoDSP p1/p8 missing validated FCOM injection")
    endif()
    set_property(SOURCE "${fcom_part}" APPEND PROPERTY
      COMPILE_DEFINITIONS CODRECOMP_X87_FCOM_FASTPATH)
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
