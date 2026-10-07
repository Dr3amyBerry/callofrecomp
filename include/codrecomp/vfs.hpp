#ifndef CODRECOMP_VFS_HPP
#define CODRECOMP_VFS_HPP

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <memory>
#include <string>
#include <unordered_map>
#include <vector>

namespace codrecomp::vfs {

enum class Error {
    none,
    invalid_path,
    not_found,
    io_error,
    invalid_archive,
    unsupported_entry,
    too_large,
};

struct Result {
    Error error = Error::none;
    std::vector<std::uint8_t> bytes;
    std::string detail;
    explicit operator bool() const noexcept { return error == Error::none; }
};

struct MountResult {
    Error error = Error::none;
    std::size_t entries = 0;
    std::string detail;
    explicit operator bool() const noexcept { return error == Error::none; }
};

struct StreamReadResult {
    Error error = Error::none;
    std::size_t bytes = 0;
    bool eof = false;
    explicit operator bool() const noexcept { return error == Error::none; }
};

// Sequential read cursor over a loose file or PK3 member.
// No full-file allocation, no seek support yet. CRC is checked at end-of-stream.
class ReadStream {
public:
    ~ReadStream();
    ReadStream(const ReadStream&) = delete;
    ReadStream& operator=(const ReadStream&) = delete;
    std::uint64_t size() const noexcept;
    std::uint64_t position() const noexcept;
    StreamReadResult read(void* output, std::size_t max_bytes);
private:
    struct State;
    std::unique_ptr<State> state_;
    explicit ReadStream(std::unique_ptr<State> state);
    friend class Vfs;
};

struct OpenStreamResult {
    Error error = Error::none;
    std::unique_ptr<ReadStream> stream;
    std::string detail;
    explicit operator bool() const noexcept {
        return error == Error::none && stream != nullptr;
    }
};

// Data-only virtual filesystem, not a claim of the original CoD FS behavior.
// Latest mount wins; all reads bounded; archives never extracted to host disk.
class Vfs {
public:
    static constexpr std::size_t default_max_file_bytes = 64u * 1024u * 1024u;

    MountResult mount_directory(const std::filesystem::path& root);
    MountResult mount_pk3(const std::filesystem::path& archive);
    OpenStreamResult open_stream(const std::string& logical_path,
                                 std::size_t max_bytes = default_max_file_bytes) const;
    Result read_file(const std::string& logical_path,
                     std::size_t max_bytes = default_max_file_bytes) const;
    std::size_t mount_count() const noexcept { return mounts_.size(); }

private:
    struct Entry {
        std::uint64_t local_offset = 0;
        std::uint64_t compressed_size = 0;
        std::uint64_t uncompressed_size = 0;
        std::uint32_t crc32 = 0;
        std::uint16_t method = 0;
        std::uint16_t flags = 0;
        std::string normalized_name;
    };
    struct Mount {
        bool is_archive = false;
        std::filesystem::path path;
        std::uint64_t file_size = 0;
        std::unordered_map<std::string, Entry> entries;
    };
    std::vector<Mount> mounts_;
};

} // namespace codrecomp::vfs
#endif // CODRECOMP_VFS_HPP
