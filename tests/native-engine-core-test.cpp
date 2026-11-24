#include "engine_core.h"
#include "emoji_index.h"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>

namespace {

[[noreturn]] void fail(const std::string &message) {
    std::cerr << "FAIL: " << message << '\n';
    std::exit(1);
}

void check(bool condition, const std::string &message) {
    if (!condition) {
        fail(message);
    }
}

void type(xiapin::EngineCore &engine, const std::string &text) {
    for (char character : text) {
        check(engine.type(character).handled, "printable pinyin was rejected");
    }
}

bool contains(const std::vector<std::string> &values, const std::string &value) {
    for (const auto &item : values) {
        if (item == value) {
            return true;
        }
    }
    return false;
}

std::string readFile(const std::filesystem::path &path) {
    std::ifstream input(path, std::ios::binary);
    return {std::istreambuf_iterator<char>(input),
            std::istreambuf_iterator<char>()};
}

} // namespace

int main(int argc, char **argv) {
    check(argc == 6, "expected system dictionary, extra dictionary, model, data directory and Emoji dictionary");
    const auto emojiIndex = xiapin::EmojiIndex::load(argv[5]);
    xiapin::EngineCore engine({argv[1], argv[2], argv[3], argv[4]},
                              false, emojiIndex);

    check(!engine.selectCurrentCandidate().handled,
          "idle Space path was marked handled without a composition");

    type(engine, "xianyanbao");
    check(contains(engine.view().candidates, "显眼包"),
          "packaged hotword is absent");
    engine.escape();

    type(engine, "nihao");
    auto view = engine.view();
    check(view.preedit == "ni hao",
          "visible syllable segmentation changed: <" + view.preedit + ">");
    check(view.rawInput == "nihao", "raw input differs from typed pinyin");
    check(view.rawCursor == 5, "raw cursor did not advance while typing");
    check(!view.candidates.empty(), "nihao has no candidates");

    engine.moveLeft();
    engine.moveLeft();
    check(engine.view().rawCursor == 3, "Left did not move the cursor");
    engine.backspace();
    check(engine.view().rawInput == "niao" && engine.view().rawCursor == 2,
          "middle Backspace failed: <" + engine.view().rawInput + ">");
    engine.deleteForward();
    check(engine.view().rawInput == "nio" && engine.view().rawCursor == 2,
          "forward Delete failed: <" + engine.view().rawInput + ">");
    engine.type('h');
    check(engine.view().rawInput == "niho" && engine.view().rawCursor == 3,
          "middle insertion failed: <" + engine.view().rawInput + ">");
    engine.escape();

    type(engine, "xi'an");
    check(engine.view().rawInput == "xi'an", "apostrophe segmentation failed");
    engine.moveHome();
    engine.moveRight();
    engine.moveRight();
    engine.deleteForward();
    check(engine.view().rawInput == "xian", "apostrophe deletion failed");
    engine.type('\'');
    check(engine.view().rawInput == "xi'an", "apostrophe reinsertion failed");
    engine.moveEnd();

    auto result = engine.selectCandidate(0);
    check(result.handled, "candidate selection was rejected");
    check(!result.commit.empty(), "candidate selection did not commit");
    check(engine.empty(), "composition remained after a full commit");
    check(std::filesystem::exists(std::filesystem::path(argv[4]) / "user.dict"),
          "user dictionary was not saved");
    check(std::filesystem::exists(std::filesystem::path(argv[4]) / "user.history"),
          "user history was not saved");

    xiapin::EngineCore second({argv[1], argv[2], argv[3], argv[4]},
                              false, emojiIndex);
    type(engine, "zhongguo");
    type(second, "nihao");
    check(engine.view().rawInput == "zhongguo",
          "a second input context changed the first preedit");
    check(second.view().rawInput == "nihao",
          "input contexts do not keep independent preedits");
    check(!engine.selectCandidate(0).commit.empty(),
          "the first shared context could not learn");
    check(!second.selectCandidate(0).commit.empty(),
          "the second shared context could not learn");

    type(engine, "shi");
    check(engine.view().candidates.size() > 9,
          "pagination fixture has fewer than ten candidates");
    check(engine.pageDown().handled && engine.view().candidateCursor >= 9,
          "Page Down did not move to the second candidate page");
    result = engine.selectCandidate(engine.view().candidateCursor / 9 * 9);
    check(!result.commit.empty(), "numeric selection on a later page failed");

    type(engine, "nihaoma");
    engine.moveHome();
    for (int index = 0; index < 5; ++index) {
        engine.moveRight();
    }
    result = engine.selectCandidate(0);
    check(result.handled && result.commit.empty() && !engine.empty(),
          "partial candidate selection committed the whole composition");
    check(engine.view().rawInput == "nihaoma",
          "partial selection changed the remaining raw input");
    engine.escape();

    const auto userPath = std::filesystem::path(argv[4]) / "user.dict";
    const auto historyPath = std::filesystem::path(argv[4]) / "user.history";
    const auto userBeforeSensitive = readFile(userPath);
    const auto historyBeforeSensitive = readFile(historyPath);
    type(engine, "mima");
    engine.setSensitive(true);
    result = engine.selectCandidate(0);
    check(!result.commit.empty(), "sensitive-field input cannot commit");
    check(readFile(userPath) == userBeforeSensitive &&
              readFile(historyPath) == historyBeforeSensitive,
          "sensitive-field input changed persistent learning data");
    engine.setSensitive(false);

    const auto userBeforeEmoji = readFile(userPath);
    const auto historyBeforeEmoji = readFile(historyPath);
    type(engine, "xiaolian");
    view = engine.view();
    std::size_t emojiCandidate = view.candidates.size();
    for (std::size_t index = 0; index < view.candidates.size(); ++index) {
        if (view.candidates[index] == "😀") {
            emojiCandidate = index;
            break;
        }
    }
    check(emojiCandidate < view.candidates.size(),
          "system Chinese Emoji data did not add the grin candidate");
    check(emojiCandidate == 8,
          "Emoji candidate is not the ninth item on the first page");
    result = engine.selectCandidate(emojiCandidate);
    check(result.commit == "😀" && engine.empty(),
          "Emoji selection did not commit and clear the composition");
    check(readFile(userPath) == userBeforeEmoji &&
              readFile(historyPath) == historyBeforeEmoji,
          "Emoji selection changed LibIME learning data");

    type(engine, "nihaoxiaolian");
    engine.moveHome();
    for (int index = 0; index < 5; ++index) {
        engine.moveRight();
    }
    result = engine.selectCandidate(0);
    check(result.handled && result.commit.empty() && !engine.empty(),
          "Emoji prefix fixture did not make a partial selection");
    view = engine.view();
    emojiCandidate = view.candidates.size();
    for (std::size_t index = 0; index < view.candidates.size(); ++index) {
        if (view.candidates[index] == "😀") {
            emojiCandidate = index;
            break;
        }
    }
    check(emojiCandidate < view.candidates.size(),
          "Emoji candidate disappeared after a partial selection");
    result = engine.selectCandidate(emojiCandidate);
    check(result.commit == "你好😀" && engine.empty(),
          "Emoji selection lost the selected Chinese prefix");

    type(engine, "xiaolianma");
    engine.moveHome();
    for (int index = 0; index < 8; ++index) {
        engine.moveRight();
    }
    check(!contains(engine.view().candidates, "😀"),
          "Emoji was offered at an embedded cursor and could discard a suffix");
    engine.escape();

    type(engine, "nihao");
    result = engine.enter();
    check(result.commit == "nihao" && engine.empty(),
          "Enter did not commit raw pinyin");
    check(!engine.candidateUp().handled && !engine.candidateDown().handled &&
              !engine.pageUp().handled && !engine.pageDown().handled,
          "candidate navigation remained active after Enter committed raw pinyin");
    type(engine, "nihao");
    engine.reset();
    check(!engine.candidateUp().handled && !engine.candidateDown().handled,
          "candidate navigation remained active after reset");
    type(engine, "nihao");
    check(engine.escape().handled && engine.empty(),
          "Escape did not clear the composition");

    check(xiapin::chinesePunctuation(',') == "，", "Chinese comma is wrong");
    check(xiapin::chinesePunctuation('.') == "。", "Chinese period is wrong");
    check(xiapin::chinesePunctuation('?') == "？", "Chinese question mark is wrong");
    check(xiapin::chinesePunctuation('!') == "！", "Chinese exclamation mark is wrong");
    check(xiapin::chinesePunctuation('A').empty(),
          "ASCII letters were treated as Chinese punctuation");
    engine.setChineseMode(false);
    check(!engine.view().chineseMode, "explicit English mode failed");
    check(!engine.type('a').handled, "English mode swallowed an ASCII key");
    engine.setChineseMode(true);
    check(engine.view().chineseMode, "explicit Chinese mode failed");
    engine.toggleMode();
    check(!engine.view().chineseMode, "Shift/Ctrl+Space mode toggle failed");
    engine.toggleMode();

    check(xiapin::utf8CharacterOffset("你hao", 3) == 1,
          "UTF-8 cursor conversion failed");
    check(xiapin::utf8CharacterOffset("你hao", 5) == 3,
          "mixed UTF-8 cursor conversion failed");

    std::cout << "xiapin-native-core-ok idle-space=1 hotword=1 edit=1 candidate=1 paging=1 "
                 "partial=1 learning=1 shared=1 sensitive=1 enter=1 enter-passthrough=1 escape=1 "
                 "toggle=1 chinese-punctuation=1 emoji=1 emoji-prefix=1 emoji-learning=0\n";
    return 0;
}
