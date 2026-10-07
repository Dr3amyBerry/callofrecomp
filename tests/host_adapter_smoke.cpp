#include "codrecomp/read_only_host_adapter.hpp"
#include <cassert>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>

namespace fs = std::filesystem;
using namespace codrecomp::vfs;

int main() {
    const fs::path temp = fs::temp_directory_path() /
        ("cod_adapter_" +
         std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    fs::create_directories(temp);
    { std::ofstream file(temp / "sample.cfg", std::ios::binary); file << "0123456789"; }
    { std::ofstream empty(temp / "empty.cfg", std::ios::binary); }

    Vfs files;
    assert(files.mount_directory(temp));
    ReadOnlyHostAdapter adapter(files, 77); // Intentionally NOT a presumed COD1 mode.
    cod_host_services_t host = adapter.services();
    assert(host.context == &adapter);
    assert(host.fs_read && host.fs_open && host.fs_close);
    assert(!host.fs_write && !host.fs_rename &&
           !host.fs_getfilelist && !host.execute_console_text);

    cod_host_fs_handle_t handle = 555;
    assert(host.fs_open(host.context, "sample.cfg", &handle, 1) == -1);
    assert(handle == 0);
    assert(host.fs_open(host.context, "../secret.txt", &handle, 77) == -1);
    assert(handle == 0);
    assert(host.fs_open(host.context, "sample.cfg", &handle, 77) == 10);
    assert(handle != 0);
    char buffer[12] = {};
    assert(host.fs_read(host.context, buffer, 4, handle) == 4);
    assert(std::memcmp(buffer, "0123", 4) == 0);
    assert(host.fs_read(host.context, buffer + 4, 20, handle) == 6);
    assert(std::memcmp(buffer, "0123456789", 10) == 0);
    assert(host.fs_read(host.context, buffer, 5, handle) == 0);
    assert(host.fs_read(host.context, nullptr, 5, handle) == -1);

    cod_host_fs_handle_t empty_handle = 0;
    assert(host.fs_open(host.context, "empty.cfg", &empty_handle, 77) == 0);
    assert(empty_handle != 0);
    assert(host.fs_read(host.context, buffer, 5, empty_handle) == 0);
    host.fs_close(host.context, empty_handle);

    cod_host_fs_handle_t second = 0;
    assert(host.fs_open(host.context, "sample.cfg", &second, 77) == 10);
    assert(second != handle && second != 0);
    assert(host.fs_read(host.context, buffer, 2, second) == 2);
    assert(std::memcmp(buffer, "01", 2) == 0);
    host.fs_close(host.context, handle);
    assert(host.fs_read(host.context, buffer, 2, handle) == -1);
    assert(host.fs_read(host.context, buffer, 0, second) == 0);
    host.fs_close(host.context, second);
    fs::remove_all(temp);
    std::cout << "read-only host adapter smoke passed\n";
    return 0;
}
