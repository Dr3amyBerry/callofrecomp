#ifndef CODRECOMP_READ_ONLY_HOST_ADAPTER_HPP
#define CODRECOMP_READ_ONLY_HOST_ADAPTER_HPP

#include "codrecomp/host_services.h"
#include "codrecomp/vfs.hpp"

#include <cstddef>
#include <cstdint>
#include <mutex>
#include <unordered_map>
#include <vector>

namespace codrecomp::vfs {

// Host-only services adapter for reading VFS entries as opaque handles.
// Not the legacy game VM ABI: its 32-bit pointers cannot be cast to host pointers.
// Caller supplies the accepted mode explicitly; no original COD1 enum is assumed.
// VFS must outlive this adapter and its mounts must not be mutated concurrently.
class ReadOnlyHostAdapter {
public:
    ReadOnlyHostAdapter(const Vfs& vfs, std::int32_t accepted_read_mode)
        : vfs_(vfs), accepted_read_mode_(accepted_read_mode) {}
    ReadOnlyHostAdapter(const ReadOnlyHostAdapter&) = delete;
    ReadOnlyHostAdapter& operator=(const ReadOnlyHostAdapter&) = delete;

    // Non-owning callbacks; adapter must outlive any copy of the returned table.
    cod_host_services_t services() noexcept;

private:
    struct OpenFile {
        std::vector<std::uint8_t> bytes;
        std::size_t cursor = 0;
    };
    const Vfs& vfs_;
    std::int32_t accepted_read_mode_;
    std::mutex mutex_;
    std::unordered_map<cod_host_fs_handle_t, OpenFile> open_files_;
    cod_host_fs_handle_t next_handle_ = 1;

    static std::int32_t open_callback(void*, const char*, cod_host_fs_handle_t*, std::int32_t);
    static std::ptrdiff_t read_callback(void*, void*, std::size_t, cod_host_fs_handle_t);
    static void close_callback(void*, cod_host_fs_handle_t);

    std::int32_t open(const char*, cod_host_fs_handle_t*, std::int32_t);
    std::ptrdiff_t read(void*, std::size_t, cod_host_fs_handle_t);
    void close(cod_host_fs_handle_t);
};

} // namespace codrecomp::vfs
#endif
