#pragma once

#include <cstddef>
#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace xiapin {

class EmojiIndex {
public:
    ~EmojiIndex();

    static std::shared_ptr<const EmojiIndex> load(const std::string &path);

    std::optional<std::string>
    firstMatch(const std::vector<std::string> &words) const;
    std::size_t annotationCount() const;

private:
    class Impl;
    explicit EmojiIndex(std::unique_ptr<Impl> impl);

    std::unique_ptr<Impl> impl_;
};

} // namespace xiapin
