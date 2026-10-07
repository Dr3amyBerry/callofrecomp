#include "codrecomp/guest_memory.hpp"

#include <algorithm>
#include <limits>

namespace codrecomp::vm {
namespace {
constexpr std::uint64_t guest_end = std::uint64_t{1} << 32;
}

bool GuestMemory::map(std::uint32_t guest_base, std::uint8_t* host_base,
                      std::size_t bytes, bool writable) {
    if (guest_base == 0 || host_base == nullptr || bytes == 0 ||
        bytes > guest_end - guest_base) return false;
    const std::uint64_t end = std::uint64_t{guest_base} + bytes;
    for (const auto& r : regions_) {
        if (std::uint64_t{guest_base} < r.end && end > r.base) return false;
    }
    regions_.push_back({guest_base, end, host_base, writable});
    return true;
}

bool GuestMemory::unmap(std::uint32_t guest_base) {
    const auto it = std::find_if(regions_.begin(), regions_.end(),
                                 [guest_base](const Region& r) {
                                     return r.base == guest_base;
                                 });
    if (it == regions_.end()) return false;
    regions_.erase(it);
    return true;
}

const GuestMemory::Region* GuestMemory::region_for(
    std::uint32_t address, std::size_t bytes, bool need_writable) const {
    if (address == 0 || bytes == 0 || bytes > guest_end - address)
        return nullptr;
    const std::uint64_t end = std::uint64_t{address} + bytes;
    for (const auto& r : regions_) {
        if (address >= r.base && end <= r.end &&
            (!need_writable || r.writable)) return &r;
    }
    return nullptr;
}

const std::uint8_t* GuestMemory::read(std::uint32_t address,
                                      std::size_t bytes) const {
    const Region* r = region_for(address, bytes, false);
    return r ? r->data + static_cast<std::size_t>(address - r->base) : nullptr;
}

std::uint8_t* GuestMemory::write(std::uint32_t address, std::size_t bytes) {
    const Region* r = region_for(address, bytes, true);
    return r ? r->data + static_cast<std::size_t>(address - r->base) : nullptr;
}

std::optional<std::string> GuestMemory::c_string(std::uint32_t address,
                                                 std::size_t max_bytes) const {
    if (!max_bytes) return std::nullopt;
    const Region* r = region_for(address, 1, false);
    if (!r) return std::nullopt;
    const std::size_t available = static_cast<std::size_t>(r->end - address);
    const auto* start = r->data + static_cast<std::size_t>(address - r->base);
    const auto length = std::min(available, max_bytes);
    for (std::size_t n = 0; n < length; ++n)
        if (start[n] == 0)
            return std::string(reinterpret_cast<const char*>(start), n);
    return std::nullopt;
}

bool GuestMemory::write_u32_le(std::uint32_t address, std::uint32_t value) {
    auto* p = write(address, 4);
    if (!p) return false;
    for (unsigned i = 0; i < 4; ++i)
        p[i] = static_cast<std::uint8_t>(value >> (8 * i));
    return true;
}

bool GuestMemory::read_u32_le(std::uint32_t address,
                              std::uint32_t& out) const {
    const auto* p = read(address, 4);
    if (!p) return false;
    out = 0;
    for (unsigned i = 0; i < 4; ++i)
        out |= std::uint32_t{p[i]} << (8 * i);
    return true;
}

} // namespace codrecomp::vm
