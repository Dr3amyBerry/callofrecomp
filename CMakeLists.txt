cmake_minimum_required(VERSION 3.20)

project(callofrecomp LANGUAGES C CXX)

add_library(codrecomp_abi INTERFACE)
target_include_directories(codrecomp_abi INTERFACE
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
)

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
endif()
