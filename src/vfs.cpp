#include "codrecomp/vfs.hpp"

#include <algorithm>
#include <array>
#include <fstream>
#include <limits>
#include <optional>
#include <string_view>
#include <system_error>
#include <zlib.h>

namespace codrecomp::vfs {
namespace {

constexpr std::uint32_t central_signature = 0x02014b50;
constexpr std::uint32_t local_signature = 0x04034b50;
constexpr std::uint32_t eocd_signature = 0x06054b50;
constexpr std::size_t max_central_bytes = 64u * 1024u * 1024u;

std::uint16_t u16(const std::uint8_t* p) {
    return static_cast<std::uint16_t>(p[0]) | static_cast<std::uint16_t>(p[1] << 8);
}
std::uint32_t u32(const std::uint8_t* p) {
    return static_cast<std::uint32_t>(u16(p)) | (static_cast<std::uint32_t>(u16(p + 2)) << 16);
}
struct LogicalPath { std::string display; std::string key; };

std::optional<LogicalPath> normalize(std::string_view raw) {
    if (raw.empty() || raw.size() > 1024 || raw.front() == '/' || raw.front() == '\\')
        return std::nullopt;
    LogicalPath p;
    std::string segment;
    auto append = [&]() -> bool {
        if (segment == "..") return false;
        if (segment.empty() || segment == ".") { segment.clear(); return true; }
        if (!p.display.empty()) { p.display += '/'; p.key += '/'; }
        p.display += segment;
        for (unsigned char c : segment)
            p.key += static_cast<char>(c >= 'A' && c <= 'Z' ? c + 32 : c);
        segment.clear();
        return true;
    };
    for (unsigned char c : raw) {
        if (c == ':' || c < 32 || c == 127) return std::nullopt;
        if (c == '/' || c == '\\') {
            if (!append()) return std::nullopt;
        } else {
            segment += static_cast<char>(c);
        }
    }
    if (!append() || p.display.empty()) return std::nullopt;
    return p;
}

bool beneath(const std::filesystem::path& root, const std::filesystem::path& candidate) {
    auto r = root.begin();
    auto c = candidate.begin();
    for (; r != root.end(); ++r, ++c) {
        if (c == candidate.end() || *r != *c) return false;
    }
    return true;
}

bool seek_read(std::ifstream& stream, std::uint64_t offset, std::uint8_t* dst, std::size_t count) {
    if (offset > static_cast<std::uint64_t>(std::numeric_limits<std::streamoff>::max()) ||
        count > static_cast<std::size_t>(std::numeric_limits<std::streamsize>::max()))
        return false;
    stream.clear();
    stream.seekg(static_cast<std::streamoff>(offset));
    if (!stream) return false;
    if (count == 0) return true;
    stream.read(reinterpret_cast<char*>(dst), static_cast<std::streamsize>(count));
    return static_cast<std::size_t>(stream.gcount()) == count;
}

Result failure(Error error, std::string detail) {
    return {error, {}, std::move(detail)};
}
MountResult mount_failure(Error error, std::string detail) {
    return {error, 0, std::move(detail)};
}

} // namespace

MountResult Vfs::mount_directory(const std::filesystem::path& root) {
    std::error_code ec;
    if (!std::filesystem::is_directory(root, ec))
        return mount_failure(Error::io_error, "mount root is not a directory");
    const auto canonical = std::filesystem::canonical(root, ec);
    if (ec) return mount_failure(Error::io_error, "could not resolve mount directory");
    Mount mount;
    mount.path = canonical;
    mounts_.push_back(std::move(mount));
    return {};
}

MountResult Vfs::mount_pk3(const std::filesystem::path& archive) {
    std::error_code ec;
    const auto canonical = std::filesystem::canonical(archive, ec);
    if (ec || !std::filesystem::is_regular_file(canonical, ec))
        return mount_failure(Error::io_error, "PK3 archive not accessible");
    const auto size = std::filesystem::file_size(canonical, ec);
    if (ec || size < 22) return mount_failure(Error::invalid_archive, "PK3 is too small");

    std::ifstream file(canonical, std::ios::binary);
    if (!file) return mount_failure(Error::io_error, "cannot open PK3");
    const auto tail_size = static_cast<std::size_t>(std::min<std::uint64_t>(size, 65535u + 22u));
    std::vector<std::uint8_t> tail(tail_size);
    if (!seek_read(file, size - tail_size, tail.data(), tail.size()))
        return mount_failure(Error::io_error, "cannot read PK3 footer");

    std::optional<std::size_t> eocd;
    for (std::size_t pos = tail.size() - 22; ; --pos) {
        if (u32(tail.data() + pos) == eocd_signature &&
            pos + 22u + u16(tail.data() + pos + 20) == tail.size()) {
            eocd = pos;
            break;
        }
        if (pos == 0) break;
    }
    if (!eocd) return mount_failure(Error::invalid_archive, "missing valid end-of-central-directory record");
    const auto* e = tail.data() + *eocd;
    const std::uint16_t disk = u16(e + 4), central_disk = u16(e + 6);
    const std::size_t disk_entries = u16(e + 8), total_entries = u16(e + 10);
    const std::uint64_t central_size = u32(e + 12), central_offset = u32(e + 16);
    const std::uint64_t footer_offset = size - tail_size + *eocd;
    if (disk || central_disk || disk_entries != total_entries ||
        central_size > max_central_bytes || central_offset > footer_offset ||
        central_size > footer_offset - central_offset ||
        central_size == 0xffffffffu || central_offset == 0xffffffffu)
        return mount_failure(Error::invalid_archive, "unsupported disk/ZIP64 layout or invalid central directory");

    std::vector<std::uint8_t> directory(static_cast<std::size_t>(central_size));
    if (!seek_read(file, central_offset, directory.data(), directory.size()))
        return mount_failure(Error::io_error, "cannot read central directory");
    Mount mount;
    mount.is_archive = true;
    mount.path = canonical;
    mount.file_size = size;
    std::size_t pos = 0;
    for (std::size_t index = 0; index < total_entries; ++index) {
        if (pos > directory.size() || directory.size() - pos < 46 ||
            u32(directory.data() + pos) != central_signature)
            return mount_failure(Error::invalid_archive, "truncated/invalid central directory entry");
        const auto* c = directory.data() + pos;
        const auto flags = u16(c + 8), method = u16(c + 10);
        const auto crc = u32(c + 16);
        const auto compressed = u32(c + 20), uncompressed = u32(c + 24);
        const auto name_length = u16(c + 28), extra = u16(c + 30), comment = u16(c + 32);
        const auto starting_disk = u16(c + 34);
        const auto local_offset = u32(c + 42);
        const std::uint64_t record_size = 46ull + name_length + extra + comment;
        if (record_size > directory.size() - pos || starting_disk != 0 ||
            compressed == 0xffffffffu || uncompressed == 0xffffffffu ||
            local_offset == 0xffffffffu || local_offset >= central_offset)
            return mount_failure(Error::invalid_archive, "invalid central directory entry metadata");
        const std::string_view filename(reinterpret_cast<const char*>(c + 46), name_length);
        if (filename.empty()) return mount_failure(Error::invalid_archive, "empty PK3 member name");
        if (filename.back() != '/' && filename.back() != '\\') {
            const auto key = normalize(filename);
            if (!key) return mount_failure(Error::invalid_archive, "unsafe PK3 member path");
            mount.entries[key->key] = Entry{
                local_offset, compressed, uncompressed, crc, method, flags, key->key
            };
        }
        pos += static_cast<std::size_t>(record_size);
    }
    if (pos != directory.size())
        return mount_failure(Error::invalid_archive, "central directory entry count mismatch");
    const std::size_t entries = mount.entries.size();
    mounts_.push_back(std::move(mount));
    return {Error::none, entries, {}};
}

Result Vfs::read_file(const std::string& logical_path, std::size_t max_bytes) const {
    auto path = normalize(logical_path);
    if (!path) return failure(Error::invalid_path, "unsafe or empty logical path");
    max_bytes = std::min(max_bytes, default_max_file_bytes);
    for (auto mount_it = mounts_.rbegin(); mount_it != mounts_.rend(); ++mount_it) {
        const Mount& mount = *mount_it;
        if (!mount.is_archive) {
            std::error_code ec;
            const auto candidate = std::filesystem::weakly_canonical(mount.path / path->display, ec);
            if (ec || !beneath(mount.path, candidate))
                return failure(Error::invalid_path, "path resolves outside mounted directory");
            if (!std::filesystem::is_regular_file(candidate, ec)) continue;
            const auto size = std::filesystem::file_size(candidate, ec);
            if (ec) return failure(Error::io_error, "cannot get loose file size");
            if (size > max_bytes) return failure(Error::too_large, "loose file exceeds read limit");
            std::ifstream file(candidate, std::ios::binary);
            if (!file) return failure(Error::io_error, "cannot open loose file");
            Result result;
            result.bytes.resize(static_cast<std::size_t>(size));
            if (!seek_read(file, 0, result.bytes.data(), result.bytes.size()))
                return failure(Error::io_error, "cannot read complete loose file");
            return result;
        }
        auto entry_it = mount.entries.find(path->key);
        if (entry_it == mount.entries.end()) continue;
        const Entry& entry = entry_it->second;
        if (entry.flags & 1) return failure(Error::unsupported_entry, "encrypted PK3 member not supported");
        if (entry.method != 0 && entry.method != 8)
            return failure(Error::unsupported_entry, "PK3 member uses unknown compression method");
        if (entry.uncompressed_size > max_bytes ||
            entry.compressed_size > default_max_file_bytes)
            return failure(Error::too_large, "PK3 member exceeds per-read limit");
        if (entry.local_offset >= mount.file_size || mount.file_size - entry.local_offset < 30)
            return failure(Error::invalid_archive, "invalid local file header offset");

        std::ifstream file(mount.path, std::ios::binary);
        if (!file) return failure(Error::io_error, "cannot reopen PK3");
        std::array<std::uint8_t, 30> local{};
        if (!seek_read(file, entry.local_offset, local.data(), local.size()) ||
            u32(local.data()) != local_signature)
            return failure(Error::invalid_archive, "missing PK3 local file header");
        if (u16(local.data() + 8) != entry.method)
            return failure(Error::invalid_archive, "local/central compression mismatch");
        const std::uint64_t local_name_size = u16(local.data() + 26);
        if (local_name_size > 1024 || local_name_size > mount.file_size - entry.local_offset - 30)
            return failure(Error::invalid_archive, "invalid local member name");
        std::string local_name(static_cast<std::size_t>(local_name_size), '\0');
        if (!seek_read(file, entry.local_offset + 30,
                       reinterpret_cast<std::uint8_t*>(local_name.data()), local_name.size()))
            return failure(Error::invalid_archive, "cannot read local member name");
        const auto normalized_local = normalize(local_name);
        if (!normalized_local || normalized_local->key != entry.normalized_name)
            return failure(Error::invalid_archive, "local and central member names differ");
        const std::uint64_t payload_offset = entry.local_offset + 30ull +
            u16(local.data() + 26) + u16(local.data() + 28);
        if (payload_offset > mount.file_size || entry.compressed_size > mount.file_size - payload_offset)
            return failure(Error::invalid_archive, "PK3 payload overflows archive size");
        std::vector<std::uint8_t> compressed(static_cast<std::size_t>(entry.compressed_size));
        if (!seek_read(file, payload_offset, compressed.data(), compressed.size()))
            return failure(Error::io_error, "cannot read PK3 payload");
        Result result;
        result.bytes.resize(static_cast<std::size_t>(entry.uncompressed_size));
        if (entry.method == 0) {
            if (entry.compressed_size != entry.uncompressed_size)
                return failure(Error::invalid_archive, "stored member has inconsistent size");
            result.bytes = std::move(compressed);
        } else {
            z_stream stream{};
            stream.next_in = compressed.data();
            stream.avail_in = static_cast<uInt>(compressed.size());
            std::uint8_t empty = 0;
            stream.next_out = result.bytes.empty() ? &empty : result.bytes.data();
            stream.avail_out = static_cast<uInt>(result.bytes.empty() ? 1 : result.bytes.size());
            if (inflateInit2(&stream, -MAX_WBITS) != Z_OK)
                return failure(Error::io_error, "zlib inflater setup failed");
            const int status = inflate(&stream, Z_FINISH);
            const std::uint64_t written = stream.total_out;
            const std::uint64_t consumed = stream.total_in;
            inflateEnd(&stream);
            if (status != Z_STREAM_END || written != entry.uncompressed_size ||
                consumed != entry.compressed_size)
                return failure(Error::invalid_archive, "bad deflated PK3 payload size or stream");
        }
        auto checksum = ::crc32(0L, Z_NULL, 0);
        checksum = ::crc32(checksum, result.bytes.data(), static_cast<uInt>(result.bytes.size()));
        if (checksum != entry.crc32)
            return failure(Error::invalid_archive, "PK3 CRC-32 mismatch");
        return result;
    }
    return failure(Error::not_found, "logical path not found in mounted sources");
}

#include "vfs_stream_impl.inc"

} // namespace codrecomp::vfs
