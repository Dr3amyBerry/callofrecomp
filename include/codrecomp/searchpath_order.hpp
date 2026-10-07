#ifndef CODRECOMP_SEARCHPATH_ORDER_HPP
#define CODRECOMP_SEARCHPATH_ORDER_HPP

#include <cstddef>
#include <cstdint>
#include <vector>

namespace codrecomp::fs {

// Evidence-based insertion algorithm at CoDSP.exe VA 0x004248B0.
// class_flag mirrors node+0x0C; its semantic meaning is NOT yet established.
// Entries are listed head-first, matching the original traversal order.
struct SearchpathEntry {
    std::uint64_t id;
    bool class_flag;
};

class SearchpathOrder {
public:
    bool insert(SearchpathEntry candidate);
    const std::vector<SearchpathEntry>& entries() const noexcept { return items_; }
private:
    std::vector<SearchpathEntry> items_;
};

} // namespace codrecomp::fs
#endif
