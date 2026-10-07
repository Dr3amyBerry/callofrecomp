#include "codrecomp/legacy_fs_read_bridge.hpp"
#include "codrecomp/game_sp_syscalls.h"

#include <algorithm>
#include <cstring>
#include <limits>
#include <string>
#include <vector>

namespace codrecomp::vm {
namespace {
BridgeResult fail(BridgeError error) {
    return {error, std::numeric_limits<cod_vm_word32_t>::max()};
}
} // namespace

LegacyFsReadBridge::~LegacyFsReadBridge() {
    if (host_.fs_close) {
        for (const auto handle : open_handles_)
            host_.fs_close(host_.context, handle);
    }
}

BridgeResult LegacyFsReadBridge::dispatch(
    const cod_vm_word32_t* words, std::size_t word_count,
    GuestMemory& memory) {
    if (!words || word_count == 0) return fail(BridgeError::invalid_arguments);
    switch (words[0]) {
        case COD_SP_G_FS_FOPEN_FILE:
            if (word_count != 4) return fail(BridgeError::invalid_arguments);
            return open(words + 1, memory);
        case COD_SP_G_FS_READ:
            if (word_count != 4) return fail(BridgeError::invalid_arguments);
            return read(words + 1, memory);
        case COD_SP_G_FS_FCLOSE_FILE:
            if (word_count != 2) return fail(BridgeError::invalid_arguments);
            return close(words + 1);
        default:
            return fail(BridgeError::unsupported_syscall);
    }
}

BridgeResult LegacyFsReadBridge::open(
    const cod_vm_word32_t* args, GuestMemory& memory) {
    if (args[2] != fs_read_mode) return fail(BridgeError::unsupported_mode);
    if (!host_.fs_open || !host_.fs_close)
        return fail(BridgeError::missing_service);
    if (!memory.write(args[1], 4))
        return fail(BridgeError::invalid_guest_memory);
    const auto name = memory.c_string(args[0]);
    if (!name || name->empty()) return fail(BridgeError::invalid_guest_memory);
    if (open_handles_.size() >= max_open_files)
        return fail(BridgeError::resource_limit);

    cod_host_fs_handle_t handle = 0;
    const std::int32_t length =
        host_.fs_open(host_.context, name->c_str(), &handle, 0);
    if (length < 0 || handle == 0 || open_handles_.count(handle)) {
        // Never close a handle already tracked by this bridge: a broken
        // backend that reused it must not corrupt a live open file.
        if (handle != 0 && !open_handles_.count(handle))
            host_.fs_close(host_.context, handle);
        return fail(BridgeError::service_failure);
    }
    if (!memory.write_u32_le(args[1], handle)) {
        host_.fs_close(host_.context, handle);
        return fail(BridgeError::invalid_guest_memory);
    }
    open_handles_.insert(handle);
    return {BridgeError::none, static_cast<cod_vm_word32_t>(length)};
}

BridgeResult LegacyFsReadBridge::read(
    const cod_vm_word32_t* args, GuestMemory& memory) {
    if (!host_.fs_read) return fail(BridgeError::missing_service);
    const std::uint32_t requested = args[1];
    const cod_host_fs_handle_t handle = args[2];
    if (!open_handles_.count(handle)) return fail(BridgeError::invalid_handle);
    if (requested > max_read_bytes) return fail(BridgeError::resource_limit);
    if (requested == 0) return {BridgeError::none, 0};
    auto* guest_dst = memory.write(args[0], requested);
    if (!guest_dst) return fail(BridgeError::invalid_guest_memory);

    // A service failure or unexpected EOF does not partially modify the
    // guest's destination buffer. The host cursor MAY have advanced.
    std::vector<std::uint8_t> staging(requested);
    std::size_t copied = 0;
    while (copied < requested) {
        const auto amount = host_.fs_read(
            host_.context, staging.data() + copied, requested - copied, handle);
        if (amount < 0) return fail(BridgeError::service_failure);
        if (amount == 0) return fail(BridgeError::short_read);
        if (static_cast<std::size_t>(amount) > requested - copied)
            return fail(BridgeError::service_failure);
        copied += static_cast<std::size_t>(amount);
    }
    std::memcpy(guest_dst, staging.data(), staging.size());
    // The observed SP game syscall handler 22 forces EAX=0 on return.
    return {BridgeError::none, 0};
}

BridgeResult LegacyFsReadBridge::close(const cod_vm_word32_t* args) {
    if (!host_.fs_close) return fail(BridgeError::missing_service);
    const cod_host_fs_handle_t handle = args[0];
    const auto it = open_handles_.find(handle);
    if (it == open_handles_.end()) return fail(BridgeError::invalid_handle);
    open_handles_.erase(it);
    host_.fs_close(host_.context, handle);
    // The observed SP game syscall handler 37 forces EAX=0 on return.
    return {BridgeError::none, 0};
}

} // namespace codrecomp::vm
