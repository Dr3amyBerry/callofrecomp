#ifndef CODRECOMP_SEARCHPATH_ORDER_HPP
#define CODRECOMP_SEARCHPATH_ORDER_HPP

#include <cstddef>
#include <cstdint>
#include <vector>

namespace codrecomp::fs {

// Modeled from CoDSP.exe VA 0x4248B0 and locale gates at 0x4226E7/0x422848.
// class_flag is the verified localized flag (name retained for source compatibility).
// Language index comes from node+0x10; meaningful only when localized.
struct SearchpathEntry {
    std::uint64_t id;
    bool class_flag;
    std::uint32_t language_index = 0;
};

class SearchpathOrder {
public:
    bool insert(SearchpathEntry candidate);
    const std::vector<SearchpathEntry>& entries() const noexcept { return items_; }
    // Evidence-based filtering for one observed filesystem lookup branch.
    // The gate's origin/meaning is NOT proven; true means localized nodes
    // were excluded by the branch. This does not perform actual file lookup.
    std::vector<SearchpathEntry> eligible(std::uint32_t active_language_index,
                                          bool reject_localized) const;
private:
    std::vector<SearchpathEntry> items_;
};

} // namespace codrecomp::fs
#endif
