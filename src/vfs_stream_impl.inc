// Internal Vfs streaming implementation. Included exactly once by src/vfs.cpp
// so ZIP/path indexing helpers remain shared with eager Vfs::read_file.
struct ReadStream::State {
    std::ifstream file;
    std::uint64_t payload = 0;
    std::uint64_t compressed = 0;
    std::uint64_t length = 0;
    std::uint64_t position = 0;
    std::uint64_t supplied = 0;
    std::uint32_t expected_crc = 0;
    uLong crc = ::crc32(0L, Z_NULL, 0);
    int method = -1;  // -1 loose, 0 stored ZIP, 8 raw DEFLATE
    bool finished = false;
    Error sticky_error = Error::none;
    bool has_inflater = false;
    z_stream inflater{};
    std::array<std::uint8_t, 32768> input{};
    ~State() { if (has_inflater) inflateEnd(&inflater); }
};

ReadStream::ReadStream(std::unique_ptr<State> state) : state_(std::move(state)) {}
ReadStream::~ReadStream() = default;
std::uint64_t ReadStream::size() const noexcept { return state_->length; }
std::uint64_t ReadStream::position() const noexcept { return state_->position; }

StreamReadResult ReadStream::read(void* output, std::size_t count) {
    auto& s = *state_;
    if (s.sticky_error != Error::none) return {s.sticky_error, 0, false};
    if (s.finished) return {Error::none, 0, true};
    auto fail = [&s](Error e) -> StreamReadResult {
        s.sticky_error = e;
        return {e, 0, false};
    };
    if (count == 0) return {Error::none, 0, s.position == s.length};
    if (!output) return {Error::invalid_path, 0, false};
    auto* bytes = static_cast<std::uint8_t*>(output);
    std::size_t written = 0;
    std::uint64_t remaining = std::min<std::uint64_t>(count, s.length - s.position);
    while (remaining) {
        const std::size_t chunk = static_cast<std::size_t>(
            std::min<std::uint64_t>(remaining, 32768));
        if (s.method == -1 || s.method == 0) {
            if (!seek_read(s.file, s.payload + s.position, bytes + written, chunk))
                return fail(Error::io_error);
            if (s.method == 0)
                s.crc = ::crc32(s.crc, bytes + written, static_cast<uInt>(chunk));
            s.position += chunk;
            written += chunk;
            remaining -= chunk;
            continue;
        }
        if (s.inflater.avail_in == 0 && s.supplied < s.compressed) {
            const std::size_t refill = static_cast<std::size_t>(
                std::min<std::uint64_t>(s.input.size(), s.compressed - s.supplied));
            if (!seek_read(s.file, s.payload + s.supplied, s.input.data(), refill))
                return fail(Error::io_error);
            s.supplied += refill;
            s.inflater.next_in = s.input.data();
            s.inflater.avail_in = static_cast<uInt>(refill);
        }
        s.inflater.next_out = bytes + written;
        s.inflater.avail_out = static_cast<uInt>(chunk);
        const uLong before_in = s.inflater.total_in;
        const int code = inflate(&s.inflater, Z_NO_FLUSH);
        const std::size_t produced = chunk - s.inflater.avail_out;
        if ((code != Z_OK && code != Z_STREAM_END) ||
            (produced == 0 && s.inflater.total_in == before_in))
            return fail(Error::invalid_archive);
        if (s.position + produced > s.length)
            return fail(Error::invalid_archive);
        s.crc = ::crc32(s.crc, bytes + written, static_cast<uInt>(produced));
        s.position += produced;
        written += produced;
        remaining -= produced;
        if (code == Z_STREAM_END) {
            s.finished = true;
            if (s.position != s.length || s.inflater.total_in != s.compressed ||
                static_cast<std::uint32_t>(s.crc) != s.expected_crc)
                return fail(Error::invalid_archive);
            return {Error::none, written, true};
        }
    }
    if (s.position == s.length) {
        if (s.method == 0) {
            if (s.crc != s.expected_crc) return fail(Error::invalid_archive);
            s.finished = true;
        } else if (s.method == -1) {
            s.finished = true;
        } else {
            // A raw DEFLATE terminator may require one additional inflate call
            // when the caller's output buffer filled exactly at logical EOF.
            while (!s.finished) {
                if (s.inflater.avail_in == 0 && s.supplied < s.compressed) {
                    const std::size_t refill = static_cast<std::size_t>(
                        std::min<std::uint64_t>(s.input.size(), s.compressed - s.supplied));
                    if (!seek_read(s.file, s.payload + s.supplied, s.input.data(), refill))
                        return fail(Error::io_error);
                    s.supplied += refill;
                    s.inflater.next_in = s.input.data();
                    s.inflater.avail_in = static_cast<uInt>(refill);
                }
                std::uint8_t extra = 0;
                s.inflater.next_out = &extra;
                s.inflater.avail_out = 1;
                const uLong before_in = s.inflater.total_in;
                const int code = inflate(&s.inflater, Z_NO_FLUSH);
                if (s.inflater.avail_out != 1 ||
                    (code != Z_OK && code != Z_STREAM_END) ||
                    (code != Z_STREAM_END && before_in == s.inflater.total_in))
                    return fail(Error::invalid_archive);
                if (code == Z_STREAM_END) {
                    if (s.inflater.total_in != s.compressed ||
                        static_cast<std::uint32_t>(s.crc) != s.expected_crc)
                        return fail(Error::invalid_archive);
                    s.finished = true;
                }
            }
        }
    }
    return {Error::none, written, s.finished};
}

OpenStreamResult Vfs::open_stream(const std::string& logical_path, std::size_t max_bytes) const {
    const auto path = normalize(logical_path);
    if (!path) return {Error::invalid_path, nullptr, "invalid logical path"};
    max_bytes = std::min(max_bytes, default_max_file_bytes);
    for (auto it = mounts_.rbegin(); it != mounts_.rend(); ++it) {
        const Mount& mount = *it;
        auto state = std::make_unique<ReadStream::State>();
        if (!mount.is_archive) {
            std::error_code ec;
            const auto candidate = std::filesystem::weakly_canonical(mount.path / path->display, ec);
            if (ec || !beneath(mount.path, candidate))
                return {Error::invalid_path, nullptr, "loose-file path escapes mount"};
            if (!std::filesystem::is_regular_file(candidate, ec)) continue;
            const auto size = std::filesystem::file_size(candidate, ec);
            if (ec) return {Error::io_error, nullptr, "cannot read file size"};
            if (size > max_bytes) return {Error::too_large, nullptr, "loose file exceeds limit"};
            state->file.open(candidate, std::ios::binary);
            if (!state->file) return {Error::io_error, nullptr, "cannot open loose file"};
            state->length = size;
            return {Error::none, std::unique_ptr<ReadStream>(new ReadStream(std::move(state))), {}};
        }
        const auto entry_it = mount.entries.find(path->key);
        if (entry_it == mount.entries.end()) continue;
        const Entry& entry = entry_it->second;
        if ((entry.flags & 1) || (entry.method != 0 && entry.method != 8))
            return {Error::unsupported_entry, nullptr, "unsupported encryption/compression"};
        if (entry.uncompressed_size > max_bytes ||
            entry.compressed_size > default_max_file_bytes)
            return {Error::too_large, nullptr, "member exceeds limit"};
        state->file.open(mount.path, std::ios::binary);
        if (!state->file) return {Error::io_error, nullptr, "cannot open PK3"};
        std::array<std::uint8_t, 30> header{};
        if (entry.local_offset >= mount.file_size ||
            mount.file_size - entry.local_offset < header.size() ||
            !seek_read(state->file, entry.local_offset, header.data(), header.size()) ||
            u32(header.data()) != local_signature ||
            u16(header.data() + 8) != entry.method)
            return {Error::invalid_archive, nullptr, "invalid local ZIP header"};
        const auto len = u16(header.data() + 26);
        const std::uint64_t data_at = entry.local_offset + header.size() +
            len + u16(header.data() + 28);
        if (len > 1024 || data_at > mount.file_size ||
            entry.compressed_size > mount.file_size - data_at)
            return {Error::invalid_archive, nullptr, "member bounds invalid"};
        std::string name(len, '\0');
        if (!seek_read(state->file, entry.local_offset + header.size(),
                       reinterpret_cast<std::uint8_t*>(name.data()), name.size()))
            return {Error::invalid_archive, nullptr, "member name truncated"};
        const auto local_path = normalize(name);
        if (!local_path || local_path->key != entry.normalized_name)
            return {Error::invalid_archive, nullptr, "local/central name mismatch"};
        if (entry.method == 0 && entry.compressed_size != entry.uncompressed_size)
            return {Error::invalid_archive, nullptr, "stored member size mismatch"};
        state->payload = data_at;
        state->compressed = entry.compressed_size;
        state->length = entry.uncompressed_size;
        state->expected_crc = entry.crc32;
        state->method = entry.method;
        if (state->method == 8) {
            if (inflateInit2(&state->inflater, -MAX_WBITS) != Z_OK)
                return {Error::io_error, nullptr, "zlib inflater setup failed"};
            state->has_inflater = true;
        }
        return {Error::none, std::unique_ptr<ReadStream>(new ReadStream(std::move(state))), {}};
    }
    return {Error::not_found, nullptr, "logical path not found"};
}
