#include "codrecomp/searchpath_order.hpp"
#include <cassert>
#include <cstdint>
#include <vector>

using codrecomp::fs::SearchpathOrder;

static void expect(const SearchpathOrder& s, std::vector<std::uint64_t> ids) {
    const auto& entries = s.entries();
    assert(entries.size() == ids.size());
    for (std::size_t i = 0; i < ids.size(); ++i) assert(entries[i].id == ids[i]);
}

int main() {
    SearchpathOrder s;
    assert(s.insert({1, true})); expect(s, {1});
    assert(s.insert({2, true})); expect(s, {1, 2});
    assert(s.insert({3, true})); expect(s, {1, 3, 2});
    assert(s.insert({4, false})); expect(s, {4, 1, 3, 2});
    assert(s.insert({5, false})); expect(s, {5, 4, 1, 3, 2});
    assert(s.insert({6, true})); expect(s, {5, 4, 6, 1, 3, 2});
    assert(!s.insert({6, false})); expect(s, {5, 4, 6, 1, 3, 2});
    SearchpathOrder zeros;
    assert(zeros.insert({10, false}));
    assert(zeros.insert({20, false}));
    assert(zeros.insert({30, true}));
    expect(zeros, {20, 10, 30});
    SearchpathOrder nonzero;
    assert(nonzero.insert({10, true}));
    assert(nonzero.insert({20, false}));
    expect(nonzero, {20, 10});
    // With both kinds present, plain (non-localized) entries precede
    // newly added localized entries in the observed insertion model.
    SearchpathOrder mixed;
    assert(mixed.insert({101, true}));
    assert(mixed.insert({102, false}));
    assert(mixed.insert({103, true}));
    expect(mixed, {102, 103, 101});
    return 0;
}
