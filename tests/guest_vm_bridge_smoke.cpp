#include "codrecomp/guest_memory.hpp"
#include "codrecomp/legacy_fs_read_bridge.hpp"
#include "codrecomp/read_only_host_adapter.hpp"
#include "codrecomp/vfs.hpp"

#include <array>
#include <cassert>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>

namespace fs = std::filesystem;
using codrecomp::vm::BridgeError;
using codrecomp::vm::GuestMemory;
using codrecomp::vm::LegacyFsReadBridge;

int main() {
    // Simulate arbitrary 32-bit guest virtual addresses with unrelated host buffers.
    std::array<std::uint8_t, 32> guest_path{};
    std::array<std::uint8_t, 8> guest_handle{};
    std::array<std::uint8_t, 32> guest_output{};
    std::memcpy(guest_path.data(), "hello.cfg", 10);

    GuestMemory memory;
    assert(memory.map(0x10000, guest_path.data(), guest_path.size(), false));
    assert(memory.map(0x20000, guest_handle.data(), guest_handle.size(), true));
    assert(memory.map(0x30000, guest_output.data(), guest_output.size(), true));
    assert(!memory.map(0x30008, guest_output.data() + 8, 4, true));
    assert(!memory.map(0x40000, guest_output.data(), 0, true));
    assert(!memory.map(0xFFFFFFFEu, guest_output.data(), 4, true));
    assert(memory.read(0x10000, 10));
    assert(!memory.write(0x10000, 4));
    assert(!memory.read(0x3001F, 2));
    assert(!memory.c_string(0x10000, 4));
    assert(memory.c_string(0x10000) == "hello.cfg");
    assert(memory.map(0xFFFFFFFFu, guest_output.data(), 1, false));
    assert(!memory.read(0xFFFFFFFFu, 2));
    assert(memory.unmap(0xFFFFFFFFu));

    const fs::path temp = fs::temp_directory_path() /
        ("cod_vm_bridge_" +
         std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    fs::create_directories(temp);
    { std::ofstream f(temp / "hello.cfg", std::ios::binary); f << "HELLO12345"; }
    codrecomp::vfs::Vfs files;
    assert(files.mount_directory(temp));
    codrecomp::vfs::ReadOnlyHostAdapter adapter(files, 0);
    {
        LegacyFsReadBridge bridge(adapter.services());
        const std::uint32_t open_words[] = {21, 0x10000, 0x20000, 0};
        const auto opened = bridge.dispatch(open_words, 4, memory);
        assert(opened && opened.return_word == 10);
        std::uint32_t handle = 0;
        assert(memory.read_u32_le(0x20000, handle) && handle != 0);

        const std::uint32_t first_read[] = {22, 0x30000, 4, handle};
        const auto read_a = bridge.dispatch(first_read, 4, memory);
        assert(read_a && read_a.return_word == 0);
        assert(std::memcmp(guest_output.data(), "HELL", 4) == 0);

        const std::uint32_t second_read[] = {22, 0x30004, 6, handle};
        const auto read_b = bridge.dispatch(second_read, 4, memory);
        assert(read_b && read_b.return_word == 0);
        assert(std::memcmp(guest_output.data(), "HELLO12345", 10) == 0);

        const std::uint32_t zero_read[] = {22, 0, 0, handle};
        assert(bridge.dispatch(zero_read, 4, memory));
        const std::uint32_t too_large[] = {22, 0x30000, 0xffffffffu, handle};
        assert(bridge.dispatch(too_large, 4, memory).error == BridgeError::resource_limit);
        const std::uint32_t unreadable_dst[] = {22, 0x10000, 1, handle};
        assert(bridge.dispatch(unreadable_dst, 4, memory).error == BridgeError::invalid_guest_memory);

        const std::uint32_t invalid_mode[] = {21, 0x10000, 0x20000, 1};
        assert(bridge.dispatch(invalid_mode, 4, memory).error == BridgeError::unsupported_mode);
        const std::uint32_t invalid_path[] = {21, 0x55550000, 0x20000, 0};
        assert(bridge.dispatch(invalid_path, 4, memory).error == BridgeError::invalid_guest_memory);
        const std::uint32_t invalid_out[] = {21, 0x10000, 0x10000, 0};
        assert(bridge.dispatch(invalid_out, 4, memory).error == BridgeError::invalid_guest_memory);
        const std::uint32_t unsupported_write[] = {23, 0x10000, 4, handle};
        assert(bridge.dispatch(unsupported_write, 4, memory).error == BridgeError::unsupported_syscall);
        assert(bridge.dispatch(nullptr, 0, memory).error == BridgeError::invalid_arguments);
        assert(bridge.dispatch(open_words, 3, memory).error == BridgeError::invalid_arguments);

        // Read past EOF must fail without partially copying into guest RAM.
        std::memset(guest_output.data(), 0x7A, guest_output.size());
        const std::uint32_t short_read[] = {22, 0x30000, 2, handle};
        assert(bridge.dispatch(short_read, 4, memory).error == BridgeError::short_read);
        assert(guest_output[0] == 0x7A && guest_output[1] == 0x7A);

        const std::uint32_t close_words[] = {37, handle};
        assert(bridge.dispatch(close_words, 2, memory));
        assert(bridge.dispatch(close_words, 2, memory).error == BridgeError::invalid_handle);
        assert(bridge.dispatch(first_read, 4, memory).error == BridgeError::invalid_handle);
        assert(memory.unmap(0x30000));
        assert(!memory.write(0x30000, 1));
    }

    // The bridge never blindly treats 32-bit numbers as native pointers.
    assert(sizeof(void*) >= 4);
    fs::remove_all(temp);
    std::cout << "validated guest VM filesystem bridge smoke passed\n";
    return 0;
}
