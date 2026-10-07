#include "codrecomp/searchpath_order.hpp"
#include <algorithm>
#include <cstddef>

namespace codrecomp::fs {

bool SearchpathOrder::insert(SearchpathEntry candidate) {
    if (std::any_of(items_.begin(), items_.end(), [candidate](const auto& item) {
            return item.id == candidate.id;
        })) return false;

    // CoDSP.exe 0x4248B0, with class now identified as localization:
    // non-localized (zero) -> prepend; localized (nonzero) -> insert after
    // the first node and its immediately succeeding non-localized nodes.
    // This function alone does not establish active-language filtering.
    if (!candidate.class_flag || items_.empty()) {
        items_.insert(items_.begin(), candidate);
    } else {
        std::size_t after = 0;
        while (after + 1 < items_.size() && !items_[after + 1].class_flag)
            ++after;
        items_.insert(items_.begin() + static_cast<std::ptrdiff_t>(after + 1), candidate);
    }
    return true;
}

} // namespace codrecomp::fs
