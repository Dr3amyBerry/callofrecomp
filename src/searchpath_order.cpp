#include "codrecomp/searchpath_order.hpp"
#include <algorithm>
#include <cstddef>

namespace codrecomp::fs {

bool SearchpathOrder::insert(SearchpathEntry candidate) {
    if (std::any_of(items_.begin(), items_.end(), [candidate](const auto& item) {
            return item.id == candidate.id;
        })) return false;

    // Exact model of CoDSP.exe 0x4248B0:
    // zero-valued class -> prepend;
    // nonzero class with existing head -> advance from that head over each
    // immediately succeeding zero-class node, and insert after that run.
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
