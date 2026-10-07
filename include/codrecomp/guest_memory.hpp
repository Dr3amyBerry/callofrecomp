#ifndef CODRECOMP_GUEST_MEMORY_HPP
#define CODRECOMP_GUEST_MEMORY_HPP

#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace codrecomp::vm {

// A guest 32-bit address denotes an offset into an explicitly registered
// memory region; it is NEVER cast to a host pointer. The caller owns the
// backing buffers and must keep them alive until the region is unregistered.
class GuestMemory {
public:
    bool map(std::uint32_t guest_base, std::uint8_t* host_base,
             std::size_t bytes, bool writable);
    bool unmap(std::uint32_t guest_base);

    const std::uint8_t* read(std::uint32_t address, std::size_t bytes) const;
    std::uint8_t* write(std::uint32_t address, std::size_t bytes);
    std::optional<std::string> c_string(std::uint32_t address,
                                        std::size_t max_bytes = 1024) const;

    bool write_u32_le(std::uint32_t address, std::uint32_t value);
    bool read_u32_le(std::uint32_t address, std::uint32_t& out) const;

private:
    struct Region {
        std::uint64_t base;
        std::uint64_t end;
        std::uint8_t* data;
        bool writable;
    };
    const Region* region_for(std::uint32_t address, std::size_t bytes,
                             bool need_writable) const;
    std::vector<Region> regions_;
};

} // namespace codrecomp::vm

#endif // CODRECOMP_GUEST_MEMORY_HPP
