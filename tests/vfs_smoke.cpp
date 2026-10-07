#include "codrecomp/vfs.hpp"

#include <zlib.h>
#include <cassert>
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

using codrecomp::vfs::Vfs;
using codrecomp::vfs::Error;
namespace fs = std::filesystem;

struct Member {
    std::string name;
    std::string data;
    bool deflate;
};

void append16(std::vector<std::uint8_t>& out, std::uint16_t x) {
    out.push_back(static_cast<std::uint8_t>(x));
    out.push_back(static_cast<std::uint8_t>(x >> 8));
}
void append32(std::vector<std::uint8_t>& out, std::uint32_t x) {
    append16(out, static_cast<std::uint16_t>(x));
    append16(out, static_cast<std::uint16_t>(x >> 16));
}
void append_string(std::vector<std::uint8_t>& out, const std::string& text) {
    out.insert(out.end(), text.begin(), text.end());
}

std::vector<std::uint8_t> compress_deflate(const std::string& source) {
    z_stream stream{};
    assert(deflateInit2(&stream, Z_DEFAULT_COMPRESSION, Z_DEFLATED, -MAX_WBITS, 8,
                        Z_DEFAULT_STRATEGY) == Z_OK);
    std::vector<std::uint8_t> out(compressBound(static_cast<uLong>(source.size())));
    stream.next_in = reinterpret_cast<Bytef*>(const_cast<char*>(source.data()));
    stream.avail_in = static_cast<uInt>(source.size());
    stream.next_out = out.data();
    stream.avail_out = static_cast<uInt>(out.size());
    assert(deflate(&stream, Z_FINISH) == Z_STREAM_END);
    out.resize(static_cast<std::size_t>(stream.total_out));
    deflateEnd(&stream);
    return out;
}

void make_pk3(const fs::path& path, const std::vector<Member>& members, bool bad_crc = false) {
    std::vector<std::uint8_t> archive, central;
    for (const auto& member : members) {
        const auto begin = static_cast<std::uint32_t>(archive.size());
        const auto crc = static_cast<std::uint32_t>(::crc32(
            0, reinterpret_cast<const Bytef*>(member.data.data()),
            static_cast<uInt>(member.data.size())));
        const auto payload = member.deflate ? compress_deflate(member.data) :
            std::vector<std::uint8_t>(member.data.begin(), member.data.end());
        const std::uint16_t method = member.deflate ? 8 : 0;
        append32(archive, 0x04034b50);
        append16(archive, 20); append16(archive, 0); append16(archive, method);
        append16(archive, 0); append16(archive, 0);
        append32(archive, bad_crc ? crc ^ 0xffu : crc);
        append32(archive, static_cast<std::uint32_t>(payload.size()));
        append32(archive, static_cast<std::uint32_t>(member.data.size()));
        append16(archive, static_cast<std::uint16_t>(member.name.size()));
        append16(archive, 0);
        append_string(archive, member.name);
        archive.insert(archive.end(), payload.begin(), payload.end());

        append32(central, 0x02014b50);
        append16(central, 20); append16(central, 20); append16(central, 0);
        append16(central, method); append16(central, 0); append16(central, 0);
        append32(central, bad_crc ? crc ^ 0xffu : crc);
        append32(central, static_cast<std::uint32_t>(payload.size()));
        append32(central, static_cast<std::uint32_t>(member.data.size()));
        append16(central, static_cast<std::uint16_t>(member.name.size()));
        append16(central, 0); append16(central, 0);
        append16(central, 0); append16(central, 0); append32(central, 0);
        append32(central, begin);
        append_string(central, member.name);
    }
    const auto central_offset = static_cast<std::uint32_t>(archive.size());
    archive.insert(archive.end(), central.begin(), central.end());
    append32(archive, 0x06054b50);
    append16(archive, 0); append16(archive, 0);
    append16(archive, static_cast<std::uint16_t>(members.size()));
    append16(archive, static_cast<std::uint16_t>(members.size()));
    append32(archive, static_cast<std::uint32_t>(central.size()));
    append32(archive, central_offset); append16(archive, 0);
    std::ofstream file(path, std::ios::binary | std::ios::trunc);
    file.write(reinterpret_cast<const char*>(archive.data()),
               static_cast<std::streamsize>(archive.size()));
    assert(file.good());
}

std::string text(const codrecomp::vfs::Result& result) {
    return std::string(result.bytes.begin(), result.bytes.end());
}

int main(int argc, char** argv) {
    const fs::path test_dir = fs::temp_directory_path() /
        ("cod_vfs_smoke_" +
         std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    fs::create_directories(test_dir / "loose" / "scripts");
    make_pk3(test_dir / "base.pk3",
             {{"Textures/HELLO.TXT", "hello-from-base", true},
              {"scripts/empty.cfg", "", false},
              {"scripts/hello.cfg", "hello-from-archive", false}});
    make_pk3(test_dir / "patch.pk3", {{"textures/hello.txt", "hello-from-patch", true}});
    make_pk3(test_dir / "bad-crc.pk3", {{"textures/bad.txt", "data", false}}, true);
    make_pk3(test_dir / "bad-deflated-crc.pk3",
             {{"broken_compressed.cfg", "baddeflate", true}}, true);
    std::string large;
    large.reserve(151111);
    std::uint32_t seed = 0x9385f873;
    for (std::size_t i = 0; i < 151111; ++i) {
        seed ^= seed << 13;
        seed ^= seed >> 17;
        seed ^= seed << 5;
        large.push_back(static_cast<char>(seed & 255u));
    }
    make_pk3(test_dir / "large.pk3", {{"raw/huge.bin", large, true}});

    make_pk3(test_dir / "traversal.pk3", {{"../escaping.txt", "oops", false}});
    { std::ofstream bad(test_dir / "invalid.pk3"); bad << "not zip"; }
    { std::ofstream loose(test_dir / "loose" / "scripts" / "hello.cfg"); loose << "hello-from-loose"; }

    Vfs vfs;
    assert(!vfs.mount_pk3(test_dir / "invalid.pk3"));
    assert(!vfs.mount_pk3(test_dir / "traversal.pk3"));
    assert(vfs.mount_count() == 0);
    const auto base = vfs.mount_pk3(test_dir / "base.pk3");
    assert(base && base.entries == 3);
    assert(text(vfs.read_file("tEXTURES\\hello.txt")) == "hello-from-base");
    assert(vfs.read_file("scripts/empty.cfg"));
    assert(vfs.read_file("scripts/empty.cfg").bytes.empty());
    assert(vfs.read_file("missing.txt").error == Error::not_found);
    assert(vfs.read_file("../etc/passwd").error == Error::invalid_path);
    assert(vfs.read_file("/etc/passwd").error == Error::invalid_path);
    assert(vfs.read_file("C:/evil.dat").error == Error::invalid_path);
    assert(vfs.read_file("textures/hello.txt", 3).error == Error::too_large);

    assert(vfs.mount_directory(test_dir / "loose"));
    assert(text(vfs.read_file("scripts/hello.cfg")) == "hello-from-loose");
    assert(vfs.mount_pk3(test_dir / "patch.pk3"));
    assert(text(vfs.read_file("textures/hello.txt")) == "hello-from-patch");
    assert(vfs.mount_pk3(test_dir / "bad-crc.pk3"));
    assert(vfs.read_file("textures/bad.txt").error == Error::invalid_archive);

    // Sequential streaming over ZIP32 stored/deflated entries and loose files.
    auto streamed = vfs.open_stream("textures/hello.txt");
    assert(streamed && streamed.stream->size() == std::string("hello-from-patch").size());
    char streamed_data[48] = {};
    auto r1 = streamed.stream->read(streamed_data, 3);
    auto r2 = streamed.stream->read(streamed_data + 3, 8);
    auto r3 = streamed.stream->read(streamed_data + 11, 32);
    assert(r1 && r1.bytes == 3 && !r1.eof);
    assert(r2 && r2.bytes == 8 && !r2.eof);
    assert(r3 && r3.bytes == 5 && r3.eof);
    assert(std::string(streamed_data, 16) == "hello-from-patch");
    assert(streamed.stream->read(streamed_data, sizeof(streamed_data)).bytes == 0);
    auto stored = vfs.open_stream("scripts/empty.cfg");
    assert(stored && stored.stream->size() == 0);
    assert(stored.stream->read(streamed_data, 2).eof);
    auto bad_crc = vfs.open_stream("textures/bad.txt");
    assert(bad_crc);
    assert(bad_crc.stream->read(streamed_data, sizeof(streamed_data)).error == Error::invalid_archive);
    // A failed stream stays failed; cannot resume silently after bad CRC.
    assert(bad_crc.stream->read(streamed_data, 1).error == Error::invalid_archive);
    auto loose_stream = vfs.open_stream("scripts/hello.cfg");
    assert(loose_stream);
    auto loose_read = loose_stream.stream->read(streamed_data, 30);
    assert(loose_read && loose_read.bytes == 16 && loose_read.eof);
    assert(std::string(streamed_data, 16) == "hello-from-loose");
    assert(vfs.open_stream("../other").error == Error::invalid_path);
    assert(vfs.open_stream("textures/hello.txt", 4).error == Error::too_large);

    // Over 150 KiB of incompressible source: multiple input and output refills.
    Vfs big;
    assert(big.mount_pk3(test_dir / "large.pk3"));
    auto big_stream = big.open_stream("RAW/HUGE.BIN");
    assert(big_stream && big_stream.stream->size() == large.size());
    std::string recovered(large.size(), ' ');
    std::size_t cursor = 0;
    for (const std::size_t step : {1u, 7u, 65537u, 32768u, 33000u, 100000u}) {
        if (cursor == recovered.size()) break;
        auto read_result = big_stream.stream->read(&recovered[cursor],
            std::min(step, recovered.size() - cursor));
        assert(read_result && read_result.bytes > 0);
        cursor += read_result.bytes;
    }
    assert(cursor == recovered.size() && recovered == large);
    assert(big_stream.stream->read(&recovered[0], 1).eof);
    assert(big.mount_pk3(test_dir / "bad-deflated-crc.pk3"));
    auto bad_deflate = big.open_stream("broken_compressed.cfg");
    assert(bad_deflate);
    assert(bad_deflate.stream->read(&recovered[0], recovered.size()).error == Error::invalid_archive);
    assert(bad_deflate.stream->read(&recovered[0], 1).error == Error::invalid_archive);

    std::error_code ec;
    fs::create_symlink(test_dir / "base.pk3", test_dir / "loose" / "scripts" / "escape.cfg", ec);
    if (!ec) assert(vfs.read_file("scripts/escape.cfg").error == Error::invalid_path);

    // Optional user-owned original PK3: never bundled in Git or CI.
    if (argc >= 2) {
        const fs::path original = argv[1];
        assert(fs::exists(original));
        Vfs original_vfs;
        const auto mount = original_vfs.mount_pk3(original);
        assert(mount && mount.entries > 0);
        if (original.filename() == "pakb.pk3") {
            const auto real_menu = original_vfs.read_file("ui_mp/createserver.menu");
            assert(real_menu && real_menu.bytes.size() == 27514);
            const auto real_dll = original_vfs.read_file("ui_mp_x86.dll");
            assert(real_dll && real_dll.bytes.size() == 274432);
            std::cout << "real pakb contents and CRC verified\n";
        } else if (original.filename() == "localized_spanish_pak4.pk3") {
            const auto create_menu = original_vfs.read_file("ui_mp/spanish/createserver.menu");
            const auto join_menu = original_vfs.read_file("UI_MP/SPANISH/JOINserver.MENU");
            assert(create_menu && create_menu.bytes.size() == 15193);
            assert(join_menu && join_menu.bytes.size() == 35057);
            std::cout << "real localization PK3 contents and CRC verified\n";
        }
        std::cout << "original PK3 mounted: " << mount.entries << " entries\n";
    }
    fs::remove_all(test_dir);
    std::cout << "VFS smoke checks passed\n";
    return 0;
}
