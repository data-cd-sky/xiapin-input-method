#include "emoji_index.h"

#include <stdexcept>
#include <unordered_map>

#include <glib.h>

namespace xiapin {

class EmojiIndex::Impl {
public:
    std::unordered_map<std::string, std::string> annotations;
};

EmojiIndex::EmojiIndex(std::unique_ptr<Impl> impl) : impl_(std::move(impl)) {}

EmojiIndex::~EmojiIndex() = default;

std::shared_ptr<const EmojiIndex> EmojiIndex::load(const std::string &path) {
    auto impl = std::make_unique<Impl>();
    gchar *contents = nullptr;
    gsize length = 0;
    GError *error = nullptr;
    if (!g_file_get_contents(path.c_str(), &contents, &length, &error)) {
        const std::string message = error ? error->message : "unknown error";
        g_clear_error(&error);
        throw std::runtime_error("cannot read Emoji dictionary: " + message);
    }

    GVariant *outer = g_variant_ref_sink(g_variant_new_from_data(
        G_VARIANT_TYPE("(sqv)"), contents, length, FALSE, g_free, contents));
    if (!outer || !g_variant_is_normal_form(outer)) {
        if (outer) {
            g_variant_unref(outer);
        } else {
            g_free(contents);
        }
        throw std::runtime_error("invalid Emoji dictionary container");
    }

    const gchar *magic = nullptr;
    guint16 version = 0;
    GVariant *items = nullptr;
    g_variant_get(outer, "(&sqv)", &magic, &version, &items);
    if (!magic || std::string(magic) != "IBusEmojiData" || version > 5 ||
        !items || !g_variant_is_of_type(items, G_VARIANT_TYPE("av"))) {
        if (items) {
            g_variant_unref(items);
        }
        g_variant_unref(outer);
        throw std::runtime_error("unsupported Emoji dictionary format");
    }

    GVariantIter iterator;
    GVariant *record = nullptr;
    g_variant_iter_init(&iterator, items);
    while (g_variant_iter_loop(&iterator, "v", &record)) {
        const gsize childCount = g_variant_n_children(record);
        if (childCount < 6) {
            continue;
        }
        const gchar *typeName = nullptr;
        g_variant_get_child(record, 0, "&s", &typeName);
        if (!typeName || std::string(typeName) != "IBusEmojiData") {
            continue;
        }
        const gchar *emoji = nullptr;
        guint annotationCount = 0;
        g_variant_get_child(record, 2, "&s", &emoji);
        g_variant_get_child(record, 3, "u", &annotationCount);
        if (!emoji || !*emoji || annotationCount > childCount - 6) {
            continue;
        }
        for (guint index = 0; index < annotationCount; ++index) {
            const gchar *word = nullptr;
            g_variant_get_child(record, 4 + index, "&s", &word);
            if (word && *word) {
                // Keep the first entry, matching the ordering semantics used
                // by Ubuntu's generated ibus-libpinyin Emoji table.
                impl->annotations.emplace(word, emoji);
            }
        }
        const gchar *description = nullptr;
        g_variant_get_child(record, 4 + annotationCount, "&s", &description);
        if (description && *description) {
            impl->annotations.emplace(description, emoji);
        }
    }
    g_variant_unref(items);
    g_variant_unref(outer);

    if (impl->annotations.empty()) {
        throw std::runtime_error("Emoji dictionary contains no annotations");
    }
    return std::shared_ptr<const EmojiIndex>(
        new EmojiIndex(std::move(impl)));
}

std::optional<std::string>
EmojiIndex::firstMatch(const std::vector<std::string> &words) const {
    for (const auto &word : words) {
        const auto found = impl_->annotations.find(word);
        if (found != impl_->annotations.end()) {
            return found->second;
        }
    }
    return std::nullopt;
}

std::size_t EmojiIndex::annotationCount() const {
    return impl_->annotations.size();
}

} // namespace xiapin
