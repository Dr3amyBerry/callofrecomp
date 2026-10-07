#ifndef CODRECOMP_LEGACY_FS_READ_BRIDGE_HPP
#define CODRECOMP_LEGACY_FS_READ_BRIDGE_HPP

#include "codrecomp/guest_memory.hpp"
#include "codrecomp/host_services.h"
#include "codrecomp/vm_abi.h"

#include <cstddef>
#include <cstdint>
#include <unordered_set>

namespace codrecomp::vm {

// Status is kept separate from the emulated 32-bit return word. No caller
// should treat an adapter error as an original CoD engine return value.
enum class BridgeError {
    none,
    unsupported_syscall,
    invalid_arguments,
    invalid_guest_memory,
    unsupported_mode,
    invalid_handle,
    missing_service,
    service_failure,
    resource_limit,
    short_read
};

struct BridgeResult {
    BridgeError error = BridgeError::none;
    cod_vm_word32_t return_word = 0;
    explicit operator bool() const noexcept { return error == BridgeError::none; }
};

// The confirmed single-player ABI uses syscalls 21 (FS_FOPEN_FILE),
// 22 (FS_READ), and 37 (FS_FCLOSE_FILE). Guest pointers are represented by
// 32-bit addresses and resolved via GuestMemory, NEVER cast to host pointers.
//
// Only original mode 0 (read) is accepted here. Modes 1,2,3 are known
// write/append paths and deliberately rejected by this read-only adapter.
//
// The host table and its context must outlive the bridge. Calls are currently
// single-threaded; GuestMemory mappings must remain stable across dispatch.
class LegacyFsReadBridge {
public:
    explicit LegacyFsReadBridge(cod_host_services_t host) : host_(host) {}
    ~LegacyFsReadBridge();
    LegacyFsReadBridge(const LegacyFsReadBridge&) = delete;
    LegacyFsReadBridge& operator=(const LegacyFsReadBridge&) = delete;

    BridgeResult dispatch(const cod_vm_word32_t* words, std::size_t word_count,
                          GuestMemory& memory);

    static constexpr std::uint32_t fs_read_mode = 0;
    static constexpr std::size_t max_read_bytes = 1024u * 1024u;
    static constexpr std::size_t max_open_files = 4096;

private:
    BridgeResult open(const cod_vm_word32_t* args, GuestMemory& memory);
    BridgeResult read(const cod_vm_word32_t* args, GuestMemory& memory);
    BridgeResult close(const cod_vm_word32_t* args);

    cod_host_services_t host_;
    std::unordered_set<cod_host_fs_handle_t> open_handles_;
};

} // namespace codrecomp::vm

#endif // CODRECOMP_LEGACY_FS_READ_BRIDGE_HPP
