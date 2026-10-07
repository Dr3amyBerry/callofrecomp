#include "codrecomp/read_only_host_adapter.hpp"

#include <algorithm>
#include <cstring>
#include <limits>
#include <utility>

namespace codrecomp::vfs {

cod_host_services_t ReadOnlyHostAdapter::services() noexcept {
    cod_host_services_t host{};
    host.context = this;
    host.fs_open = &ReadOnlyHostAdapter::open_callback;
    host.fs_read = &ReadOnlyHostAdapter::read_callback;
    host.fs_close = &ReadOnlyHostAdapter::close_callback;
    // Write, rename, enumerate and console methods remain unimplemented.
    return host;
}

std::int32_t ReadOnlyHostAdapter::open_callback(
    void* context, const char* path, cod_host_fs_handle_t* out_handle, std::int32_t mode) {
    return static_cast<ReadOnlyHostAdapter*>(context)->open(path, out_handle, mode);
}
std::ptrdiff_t ReadOnlyHostAdapter::read_callback(
    void* context, void* output, std::size_t count, cod_host_fs_handle_t handle) {
    return static_cast<ReadOnlyHostAdapter*>(context)->read(output, count, handle);
}
void ReadOnlyHostAdapter::close_callback(void* context, cod_host_fs_handle_t handle) {
    static_cast<ReadOnlyHostAdapter*>(context)->close(handle);
}

std::int32_t ReadOnlyHostAdapter::open(
    const char* path, cod_host_fs_handle_t* out_handle, std::int32_t mode) {
    if (!out_handle) return -1;
    *out_handle = 0;
    if (mode != accepted_read_mode_ || !path) return -1;
    auto opened = vfs_.open_stream(path);
    if (!opened || opened.stream->size() >
            static_cast<std::size_t>(std::numeric_limits<std::int32_t>::max()))
        return -1;

    std::lock_guard<std::mutex> guard(mutex_);
    if (next_handle_ == 0) return -1;
    const cod_host_fs_handle_t handle = next_handle_++;
    const auto length = static_cast<std::int32_t>(opened.stream->size());
    open_files_.emplace(handle, OpenFile{std::move(opened.stream)});
    *out_handle = handle;
    // Adapter convention only: bytes in file, -1 on error. Not yet established
    // as the original game module's full error/size contract.
    return length;
}

std::ptrdiff_t ReadOnlyHostAdapter::read(void* output, std::size_t count,
                                         cod_host_fs_handle_t handle) {
    std::lock_guard<std::mutex> guard(mutex_);
    auto it = open_files_.find(handle);
    if (it == open_files_.end()) return -1;
    if (count == 0) return 0;
    if (!output) return -1;
    const auto result = it->second.stream->read(output, count);
    return result ? static_cast<std::ptrdiff_t>(result.bytes) : -1;
}

void ReadOnlyHostAdapter::close(cod_host_fs_handle_t handle) {
    std::lock_guard<std::mutex> guard(mutex_);
    open_files_.erase(handle);
}

} // namespace codrecomp::vfs
