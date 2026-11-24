#include <algorithm>
#include <exception>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>

#include <libime/core/historybigram.h>

namespace {

constexpr std::size_t MaximumHistoryLines = 128 + 8192 + 65536;

void usage(const char *program) {
    std::cerr << "Usage: " << program
              << " (--compile|--dump) <source> <destination>\n";
}

std::vector<std::string> words(const std::string &line) {
    std::istringstream input(line);
    std::vector<std::string> result;
    std::string word;
    while (input >> word) {
        result.push_back(std::move(word));
    }
    return result;
}

} // namespace

int main(int argc, char **argv) {
    if (argc != 4) {
        usage(argv[0]);
        return 2;
    }
    const std::string_view action(argv[1]);
    if (action != "--compile" && action != "--dump") {
        usage(argv[0]);
        return 2;
    }

    try {
        std::ifstream input(argv[2], std::ios::binary);
        if (!input) {
            throw std::runtime_error("cannot open history input");
        }
        std::ofstream outputFile;
        std::ostream *output = &std::cout;
        if (std::string_view(argv[3]) != "-") {
            outputFile.open(argv[3], std::ios::binary | std::ios::trunc);
            if (!outputFile) {
                throw std::runtime_error("cannot open history output");
            }
            output = &outputFile;
        }

        libime::HistoryBigram history;
        if (action == "--dump") {
            history.load(input);
            history.dump(*output);
        } else {
            std::vector<std::vector<std::string>> sentences;
            std::string line;
            while (sentences.size() < MaximumHistoryLines &&
                   std::getline(input, line)) {
                auto sentence = words(line);
                if (!sentence.empty()) {
                    sentences.push_back(std::move(sentence));
                }
            }
            for (auto iterator = sentences.rbegin();
                 iterator != sentences.rend(); ++iterator) {
                history.add(*iterator);
            }
            history.save(*output);
        }
        output->flush();
        if (!*output) {
            throw std::runtime_error("cannot write history output");
        }
    } catch (const std::exception &error) {
        std::cerr << "xiapin-history: " << error.what() << '\n';
        return 1;
    }
    return 0;
}
