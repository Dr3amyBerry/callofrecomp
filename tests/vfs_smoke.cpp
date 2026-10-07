#include "codrecomp/vfs.hpp"

#include <zlib.h>
#include <cassert>
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
        }
        std::cout << "original PK3 mounted: " << mount.entries << " entries\n";
    }
    fs::remove_all(test_dir);
    std::cout << "VFS smoke checks passed\n";
    return 0;
}
