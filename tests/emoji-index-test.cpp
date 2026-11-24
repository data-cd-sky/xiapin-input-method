#include "emoji_index.h"

#include <chrono>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

namespace {

[[noreturn]] void fail(const std::string &message) {
    std::cerr << "FAIL: " << message << '\n';
    std::exit(1);
}

} // namespace

int main(int argc, char **argv) {
    if (argc != 2) {
        fail("expected an IBus Emoji dictionary path");
    }

    const auto loadStart = std::chrono::steady_clock::now();
    const auto index = xiapin::EmojiIndex::load(argv[1]);
    const auto loadEnd = std::chrono::steady_clock::now();
    if (index->annotationCount() < 1000) {
        fail("Chinese Emoji annotation index is unexpectedly small");
    }
    const std::vector<std::string> candidates{
        "笑脸", "微笑", "高兴", "墨镜", "太阳镜", "开心", "赞", "心"};
    const auto expected = index->firstMatch(candidates);
    if (!expected || expected->empty()) {
        fail("known Chinese annotations have no Emoji match");
    }

    constexpr int QueryIterations = 100000;
    const auto queryStart = std::chrono::steady_clock::now();
    for (int iteration = 0; iteration < QueryIterations; ++iteration) {
        if (!index->firstMatch(candidates)) {
            fail("repeat lookup lost a known Emoji match");
        }
    }
    const auto queryEnd = std::chrono::steady_clock::now();
    const auto loadMicros = std::chrono::duration_cast<std::chrono::microseconds>(
                                loadEnd - loadStart)
                                .count();
    const auto queryMicros =
        std::chrono::duration_cast<std::chrono::microseconds>(queryEnd - queryStart)
            .count();
    const double averageQueryMicros =
        static_cast<double>(queryMicros) / QueryIterations;
    if (averageQueryMicros >= 1000.0) {
        fail("average Emoji lookup exceeded one millisecond");
    }

    bool missingRejected = false;
    try {
        (void)xiapin::EmojiIndex::load(
            "/nonexistent/xiapin-emoji-dictionary-for-test.dict");
    } catch (...) {
        missingRejected = true;
    }
    if (!missingRejected) {
        fail("missing Emoji dictionary was accepted");
    }
    std::cout << "xiapin-emoji-index-ok annotations="
              << index->annotationCount() << " load_ms="
              << static_cast<double>(loadMicros) / 1000.0
              << " average_query_us=" << averageQueryMicros << '\n';
    return 0;
}
