#include "engine_core.h"
#include "emoji_index.h"

#include <algorithm>
#include <atomic>
#include <cerrno>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <map>
#include <mutex>
#include <stdexcept>
#include <system_error>

#include <sys/stat.h>
#include <sys/file.h>
#include <fcntl.h>
#include <unistd.h>

#include <libime/core/userlanguagemodel.h>
#include <libime/pinyin/pinyincontext.h>
#include <libime/pinyin/pinyindictionary.h>
#include <libime/pinyin/pinyinime.h>

namespace xiapin {
namespace {

constexpr std::size_t PageSize = 9;
constexpr std::size_t EmojiSearchCandidates = PageSize - 1;
constexpr std::size_t ExtraDictionary = libime::TrieDictionary::UserDict + 1;
std::atomic_bool ChineseMode{true};

class MemoryLock {
public:
    explicit MemoryLock(const std::filesystem::path &directory) {
        std::filesystem::create_directories(directory);
        chmod(directory.c_str(), 0700);
        const auto path = directory / ".memory.lock";
        descriptor_ = open(path.c_str(), O_CREAT | O_CLOEXEC | O_RDONLY, 0600);
        if (descriptor_ < 0 || flock(descriptor_, LOCK_EX) != 0) {
            if (descriptor_ >= 0) {
                close(descriptor_);
            }
            throw std::runtime_error("cannot lock user learning data");
        }
    }

    ~MemoryLock() {
        flock(descriptor_, LOCK_UN);
        close(descriptor_);
    }

    MemoryLock(const MemoryLock &) = delete;
    MemoryLock &operator=(const MemoryLock &) = delete;

private:
    int descriptor_ = -1;
};

std::string timestampSuffix() {
    const auto value = std::chrono::system_clock::now().time_since_epoch();
    return std::to_string(
        std::chrono::duration_cast<std::chrono::seconds>(value).count());
}

void quarantine(const std::filesystem::path &path) {
    if (!std::filesystem::exists(path)) {
        return;
    }
    std::error_code error;
    std::filesystem::rename(path, path.string() + ".corrupt-" + timestampSuffix(),
                            error);
}

template <typename Writer>
void atomicSave(const std::filesystem::path &path, Writer writer) {
    std::filesystem::create_directories(path.parent_path());
    const auto temporary =
        path.string() + ".tmp-" + std::to_string(static_cast<long>(getpid()));
    try {
        {
            std::ofstream output(temporary,
                                 std::ios::binary | std::ios::trunc);
            if (!output) {
                throw std::runtime_error("cannot open temporary user data");
            }
            writer(output, temporary);
            output.flush();
            if (!output) {
                throw std::runtime_error("cannot write temporary user data");
            }
        }
        chmod(temporary.c_str(), 0600);
        std::filesystem::rename(temporary, path);
    } catch (...) {
        std::error_code ignored;
        std::filesystem::remove(temporary, ignored);
        throw;
    }
}

struct SharedEngineData {
    explicit SharedEngineData(const EnginePaths &paths) : paths(paths) {
        MemoryLock lock(paths.userDataDirectory);
        generation = readGeneration();
        auto dictionary = std::make_unique<libime::PinyinDictionary>();
        dictionary->load(libime::PinyinDictionary::SystemDict,
                         paths.systemDictionary.c_str(),
                         libime::PinyinDictFormat::Binary);

        const auto userDictionary =
            std::filesystem::path(paths.userDataDirectory) / "user.dict";
        if (std::filesystem::exists(userDictionary)) {
            try {
                dictionary->load(libime::TrieDictionary::UserDict,
                                 userDictionary.c_str(),
                                 libime::PinyinDictFormat::Binary);
            } catch (...) {
                quarantine(userDictionary);
            }
        }

        dictionary->addEmptyDict();
        dictionary->load(ExtraDictionary, paths.extraDictionary.c_str(),
                         libime::PinyinDictFormat::Binary);

        auto model =
            std::make_unique<libime::UserLanguageModel>(paths.languageModel.c_str());
        const auto history =
            std::filesystem::path(paths.userDataDirectory) / "user.history";
        if (std::filesystem::exists(history)) {
            try {
                std::ifstream input(history, std::ios::binary);
                if (!input) {
                    throw std::runtime_error("cannot open user history");
                }
                model->load(input);
            } catch (...) {
                quarantine(history);
            }
        }

        ime = std::make_unique<libime::PinyinIME>(std::move(dictionary),
                                                  std::move(model));
        ime->setNBest(32);
    }

    void save() {
        MemoryLock lock(paths.userDataDirectory);
        if (readGeneration() != generation) {
            throw std::runtime_error("learning data changed outside the engine");
        }
        const auto root = std::filesystem::path(paths.userDataDirectory);
        atomicSave(root / "user.dict", [this](std::ostream &output, const auto &) {
            ime->dict()->save(libime::TrieDictionary::UserDict, output,
                              libime::PinyinDictFormat::Binary);
        });
        atomicSave(root / "user.history", [this](std::ostream &output, const auto &) {
            ime->model()->save(output);
        });
    }

    std::string readGeneration() const {
        std::ifstream input(std::filesystem::path(paths.userDataDirectory) /
                            ".memory.generation");
        std::string value;
        std::getline(input, value);
        return value;
    }

    EnginePaths paths;
    std::string generation;
    std::unique_ptr<libime::PinyinIME> ime;
};

std::string engineDataKey(const EnginePaths &paths) {
    return paths.systemDictionary + '\n' + paths.extraDictionary + '\n' +
           paths.languageModel + '\n' + paths.userDataDirectory;
}

std::shared_ptr<SharedEngineData> sharedEngineData(const EnginePaths &paths,
                                                   bool forceReload) {
    static std::mutex mutex;
    static std::map<std::string, std::weak_ptr<SharedEngineData>> cache;
    const auto key = engineDataKey(paths);
    std::lock_guard guard(mutex);
    if (!forceReload) {
        if (auto existing = cache[key].lock()) {
            return existing;
        }
    }
    auto created = std::make_shared<SharedEngineData>(paths);
    cache[key] = created;
    return created;
}

} // namespace

class EngineCore::Impl {
public:
    explicit Impl(EnginePaths paths, bool forceReload,
                  std::shared_ptr<const EmojiIndex> emojiIndex)
        : shared_(sharedEngineData(paths, forceReload)),
          context_(std::make_unique<libime::PinyinContext>(shared_->ime.get())),
          emojiIndex_(std::move(emojiIndex)) {}

    enum class CandidateKind { LibIME, Emoji };

    struct Candidate {
        std::string text;
        CandidateKind kind;
        std::size_t sourceIndex;
    };

    std::filesystem::path userDictionaryPath() const {
        return std::filesystem::path(shared_->paths.userDataDirectory) / "user.dict";
    }

    std::filesystem::path historyPath() const {
        return std::filesystem::path(shared_->paths.userDataDirectory) / "user.history";
    }

    const std::vector<Candidate> &candidates() const {
        return candidates_;
    }

    void refreshCandidates() {
        candidates_.clear();
        std::vector<std::string> emojiSearchWords;
#ifdef XIAPIN_HAVE_LIBIME_CURSOR_CANDIDATES
        const auto &items = context_->candidatesToCursor();
        for (std::size_t index = 0; index < items.size(); ++index) {
            const auto text = items[index].toString();
            candidates_.push_back({text, CandidateKind::LibIME, index});
            if (emojiSearchWords.size() < EmojiSearchCandidates) {
                emojiSearchWords.push_back(text);
            }
        }
#else
        const auto cursor = context_->cursor();
        const auto size = context_->size();
        std::string suffix;
        if (cursor < size) {
            suffix = std::string(context_->userInput().substr(cursor));
            context_->erase(cursor, size);
        }
        const auto &items = context_->candidates();
        for (std::size_t index = 0; index < items.size(); ++index) {
            const auto text = items[index].toString();
            candidates_.push_back({text, CandidateKind::LibIME, index});
            if (emojiSearchWords.size() < EmojiSearchCandidates) {
                emojiSearchWords.push_back(text);
            }
        }
        if (!suffix.empty()) {
            context_->type(suffix);
            context_->setCursor(cursor);
        }
#endif
        std::optional<std::string> emoji;
        // Selecting an Emoji completes the composition. Do not offer one for
        // a candidate ending at an embedded cursor, where doing so would
        // otherwise discard the unconverted pinyin after that cursor.
        const auto compositionCursor = context_->cursor();
        const auto selectedLength = context_->selectedLength();
        const bool completesComposition =
            compositionCursor == context_->size() ||
            (selectedLength > 0 && compositionCursor == selectedLength);
        if (emojiIndex_ && completesComposition) {
            emoji = emojiIndex_->firstMatch(emojiSearchWords);
        }
        if (emoji) {
            const auto position = std::min(EmojiSearchCandidates,
                                           candidates_.size());
            candidates_.insert(candidates_.begin() + position,
                               {*emoji, CandidateKind::Emoji, 0});
        }
    }

    void clampCandidateCursor() {
        const auto count = candidates().size();
        if (count == 0) {
            candidateCursor_ = 0;
        } else if (candidateCursor_ >= count) {
            candidateCursor_ = count - 1;
        }
    }

    void changed() {
        candidateCursor_ = 0;
        refreshCandidates();
        dirtyView_ = true;
    }

    void clearComposition() {
        context_->clear();
        candidateCursor_ = 0;
        candidates_.clear();
        dirtyView_ = true;
    }

    EngineResult result(bool handled = true) {
        return {handled, dirtyView_, {}};
    }

    EngineResult select(std::size_t index) {
        if (index >= candidates().size()) {
            return {true, false, {}};
        }
        const auto candidate = candidates()[index];
        if (candidate.kind == CandidateKind::Emoji) {
            EngineResult output{
                true, true, context_->selectedSentence() + candidate.text};
            clearComposition();
            return output;
        }
#ifdef XIAPIN_HAVE_LIBIME_CURSOR_CANDIDATES
        context_->selectCandidatesToCursor(candidate.sourceIndex);
#else
        const auto cursor = context_->cursor();
        const auto size = context_->size();
        std::string suffix;
        if (cursor < size) {
            suffix = std::string(context_->userInput().substr(cursor));
            context_->erase(cursor, size);
        }
        if (candidate.sourceIndex >= context_->candidates().size()) {
            if (!suffix.empty()) {
                context_->type(suffix);
                context_->setCursor(cursor);
            }
            refreshCandidates();
            return {true, false, {}};
        }
        context_->select(candidate.sourceIndex);
        if (!suffix.empty()) {
            context_->type(suffix);
        }
#endif
        candidateCursor_ = 0;
        dirtyView_ = true;
        if (!context_->selected()) {
            refreshCandidates();
            return result();
        }

        EngineResult output{true, true, context_->selectedSentence()};
        if (!sensitive_) {
            context_->learn();
            try {
                saveData();
            } catch (...) {
                // Input must keep working even when persistent learning fails.
            }
        }
        clearComposition();
        return output;
    }

    EngineResult commitBest() {
        if (context_->empty()) {
            return {false, false, {}};
        }
        const auto &items = candidates();
        if (items.empty()) {
            EngineResult output{true, true, std::string(context_->userInput())};
            clearComposition();
            return output;
        }
        return select(candidateCursor_);
    }

    void saveData() {
        shared_->save();
    }

    std::shared_ptr<SharedEngineData> shared_;
    std::unique_ptr<libime::PinyinContext> context_;
    std::shared_ptr<const EmojiIndex> emojiIndex_;
    std::vector<Candidate> candidates_;
    std::size_t candidateCursor_ = 0;
    bool sensitive_ = false;
    bool dirtyView_ = false;
};

EngineCore::EngineCore(EnginePaths paths, bool forceReload,
                       std::shared_ptr<const EmojiIndex> emojiIndex)
    : impl_(std::make_unique<Impl>(std::move(paths), forceReload,
                                  std::move(emojiIndex))) {}

EngineCore::~EngineCore() = default;

EngineResult EngineCore::type(char character) {
    if (!ChineseMode.load() ||
        !(character == '\'' || (character >= 'a' && character <= 'z'))) {
        return {false, false, {}};
    }
    if (!impl_->context_->type(std::string(1, character))) {
        return {false, false, {}};
    }
    impl_->changed();
    return impl_->result();
}

EngineResult EngineCore::backspace() {
    const auto cursor = impl_->context_->cursor();
    if (cursor == 0) {
        return {false, false, {}};
    }
    impl_->context_->erase(cursor - 1, cursor);
    impl_->context_->setCursor(cursor - 1);
    impl_->changed();
    return impl_->result();
}

EngineResult EngineCore::deleteForward() {
    const auto cursor = impl_->context_->cursor();
    if (cursor >= impl_->context_->userInput().size()) {
        return {false, false, {}};
    }
    impl_->context_->erase(cursor, cursor + 1);
    impl_->context_->setCursor(cursor);
    impl_->changed();
    return impl_->result();
}

EngineResult EngineCore::moveLeft() {
    auto cursor = impl_->context_->cursor();
    if (cursor == 0) {
        return {false, false, {}};
    }
    if (cursor == impl_->context_->selectedLength()) {
        impl_->context_->cancel();
        cursor = impl_->context_->cursor();
    }
    impl_->context_->setCursor(cursor - 1);
    impl_->changed();
    return impl_->result();
}

EngineResult EngineCore::moveRight() {
    const auto cursor = impl_->context_->cursor();
    if (cursor >= impl_->context_->size()) {
        return {false, false, {}};
    }
    impl_->context_->setCursor(cursor + 1);
    impl_->changed();
    return impl_->result();
}

EngineResult EngineCore::moveHome() {
    if (impl_->context_->empty()) {
        return {false, false, {}};
    }
    impl_->context_->setCursor(impl_->context_->selectedLength());
    impl_->changed();
    return impl_->result();
}

EngineResult EngineCore::moveEnd() {
    if (impl_->context_->empty()) {
        return {false, false, {}};
    }
    impl_->context_->setCursor(impl_->context_->size());
    impl_->changed();
    return impl_->result();
}

EngineResult EngineCore::escape() {
    if (impl_->context_->empty()) {
        return {false, false, {}};
    }
    impl_->clearComposition();
    return impl_->result();
}

EngineResult EngineCore::enter() {
    if (impl_->context_->empty()) {
        return {false, false, {}};
    }
    EngineResult output{true, true, std::string(impl_->context_->userInput())};
    impl_->clearComposition();
    return output;
}

EngineResult EngineCore::selectCandidate(std::size_t index) {
    return impl_->select(index);
}

EngineResult EngineCore::selectCurrentCandidate() {
    if (impl_->context_->empty() || impl_->candidates().empty()) {
        return {false, false, {}};
    }
    return impl_->select(impl_->candidateCursor_);
}

EngineResult EngineCore::pageUp() {
    if (impl_->context_->empty()) {
        return {false, false, {}};
    }
    if (impl_->candidateCursor_ < PageSize) {
        impl_->candidateCursor_ = 0;
    } else {
        impl_->candidateCursor_ -= PageSize;
    }
    impl_->dirtyView_ = true;
    return impl_->result(!impl_->candidates().empty());
}

EngineResult EngineCore::pageDown() {
    if (impl_->context_->empty() || impl_->candidates().empty()) {
        return {false, false, {}};
    }
    impl_->candidateCursor_ = std::min(
        impl_->candidateCursor_ + PageSize, impl_->candidates().size() - 1);
    impl_->dirtyView_ = true;
    return impl_->result();
}

EngineResult EngineCore::candidateUp() {
    if (impl_->context_->empty() || impl_->candidates().empty()) {
        return {false, false, {}};
    }
    if (impl_->candidateCursor_ > 0) {
        --impl_->candidateCursor_;
    }
    impl_->dirtyView_ = true;
    return impl_->result();
}

EngineResult EngineCore::candidateDown() {
    if (impl_->context_->empty() || impl_->candidates().empty()) {
        return {false, false, {}};
    }
    impl_->candidateCursor_ = std::min(
        impl_->candidateCursor_ + 1, impl_->candidates().size() - 1);
    impl_->dirtyView_ = true;
    return impl_->result();
}

EngineResult EngineCore::commitBestAndAppend(const std::string &suffix) {
    auto result = impl_->commitBest();
    if (!result.handled) {
        return result;
    }
    result.commit += suffix;
    return result;
}

void EngineCore::reset() {
    impl_->clearComposition();
}

EngineResult EngineCore::toggleMode() {
    auto result = enter();
    ChineseMode.store(!ChineseMode.load());
    result.changed = true;
    return result;
}

EngineResult EngineCore::setChineseMode(bool enabled) {
    if (ChineseMode.load() != enabled) {
        return toggleMode();
    }
    return {false, false, {}};
}

void EngineCore::setSensitive(bool sensitive) { impl_->sensitive_ = sensitive; }

bool EngineCore::sensitive() const { return impl_->sensitive_; }

bool EngineCore::empty() const { return impl_->context_->empty(); }

EngineView EngineCore::view() const {
    EngineView output;
    output.chineseMode = ChineseMode.load();
    if (impl_->context_->empty()) {
        return output;
    }
    const auto preedit = impl_->context_->preeditWithCursor(
        libime::PinyinPreeditMode::RawText);
    output.preedit = preedit.first;
    output.cursorBytes = preedit.second;
    output.rawInput = std::string(impl_->context_->userInput());
    output.rawCursor = impl_->context_->cursor();
    output.candidateCursor = impl_->candidateCursor_;
    output.candidates.reserve(impl_->candidates().size());
    for (const auto &candidate : impl_->candidates()) {
        output.candidates.push_back(candidate.text);
    }
    output.visible = true;
    return output;
}

void EngineCore::save() { impl_->saveData(); }

std::size_t utf8CharacterOffset(const std::string &text,
                                std::size_t byteOffset) {
    byteOffset = std::min(byteOffset, text.size());
    std::size_t characters = 0;
    for (std::size_t index = 0; index < byteOffset; ++index) {
        if ((static_cast<unsigned char>(text[index]) & 0xc0U) != 0x80U) {
            ++characters;
        }
    }
    return characters;
}

std::string chinesePunctuation(char character) {
    switch (character) {
    case ',': return "，";
    case '.': return "。";
    case '?': return "？";
    case '!': return "！";
    case ';': return "；";
    case ':': return "：";
    case '(': return "（";
    case ')': return "）";
    case '[': return "【";
    case ']': return "】";
    case '<': return "《";
    case '>': return "》";
    case '\\': return "、";
    default: return {};
    }
}

} // namespace xiapin
