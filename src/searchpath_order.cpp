#include "codrecomp/searchpath_order.hpp"
#include <algorithm>
#include <cstddef>

namespace codrecomp::fs {

bool SearchpathOrder::insert(SearchpathEntry candidate) {
    if (std::any_of(items_.begin(), items_.end(), [candidate](const auto& item) {
            return item.id == candidate.id;
        })) return false;
    // Non-localized nodes prepend. Localized nodes insert after the first
    // node and its immediately following non-localized successors.
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

std::vector<SearchpathEntry> SearchpathOrder::eligible(
    std::uint32_t active_language_index, bool reject_localized) const {
    std::vector<SearchpathEntry> found;
    for (const auto& item : items_) {
        if (!item.class_flag || (!reject_localized && item.language_index == active_language_index))
            found.push_back(item);
    }
    return found;
}

} // namespace codrecomp::fs
