#pragma once

#include <cstddef>
#include <memory>
#include <string>
#include <vector>

namespace xiapin {

class EmojiIndex;

struct EnginePaths {
    std::string systemDictionary;
    std::string extraDictionary;
    std::string languageModel;
    std::string userDataDirectory;
};

struct EngineView {
    std::string preedit;
    std::size_t cursorBytes = 0;
    std::string rawInput;
    std::size_t rawCursor = 0;
    std::vector<std::string> candidates;
    std::size_t candidateCursor = 0;
    bool visible = false;
    bool chineseMode = true;
};

struct EngineResult {
    bool handled = false;
    bool changed = false;
    std::string commit;
};

class EngineCore {
public:
    explicit EngineCore(
        EnginePaths paths, bool forceReload = false,
        std::shared_ptr<const EmojiIndex> emojiIndex = nullptr);
    ~EngineCore();

    EngineCore(const EngineCore &) = delete;
    EngineCore &operator=(const EngineCore &) = delete;

    EngineResult type(char character);
    EngineResult backspace();
    EngineResult deleteForward();
    EngineResult moveLeft();
    EngineResult moveRight();
    EngineResult moveHome();
    EngineResult moveEnd();
    EngineResult escape();
    EngineResult enter();
    EngineResult selectCandidate(std::size_t index);
    EngineResult selectCurrentCandidate();
    EngineResult pageUp();
    EngineResult pageDown();
    EngineResult candidateUp();
    EngineResult candidateDown();
    EngineResult commitBestAndAppend(const std::string &suffix);

    void reset();
    EngineResult toggleMode();
    EngineResult setChineseMode(bool enabled);
    void setSensitive(bool sensitive);
    bool sensitive() const;
    bool empty() const;
    EngineView view() const;
    void save();

private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};

std::size_t utf8CharacterOffset(const std::string &text,
                                std::size_t byteOffset);
std::string chinesePunctuation(char character);

} // namespace xiapin
