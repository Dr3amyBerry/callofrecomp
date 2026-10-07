#include "codrecomp/searchpath_order.hpp"
#include <cassert>
#include <cstdint>
#include <vector>

using codrecomp::fs::SearchpathOrder;
static void expect(const std::vector<codrecomp::fs::SearchpathEntry>& xs,
                   std::vector<std::uint64_t> ids) {
    assert(xs.size() == ids.size());
    for (std::size_t i=0; i<ids.size(); ++i) assert(xs[i].id == ids[i]);
}
int main() {
    SearchpathOrder s;
    assert(s.insert({1, false}));           // plain
    assert(s.insert({2, true, 4}));         // Spanish
    assert(s.insert({3, true, 0}));         // English
    assert(s.insert({4, false}));           // later plain
    expect(s.entries(), {4, 1, 3, 2});
    expect(s.eligible(4, false), {4, 1, 2});
    expect(s.eligible(0, false), {4, 1, 3});
    expect(s.eligible(4, true), {4, 1});
    expect(s.eligible(99, false), {4, 1});
    // Insertion and language filtering are independent operations.
    expect(s.entries(), {4, 1, 3, 2});
    return 0;
}
