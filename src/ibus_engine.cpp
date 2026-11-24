#include "engine_core.h"
#include "emoji_index.h"

#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include <glib-unix.h>
#include <ibus.h>

#ifndef XIAPIN_DATA_DIR
#define XIAPIN_DATA_DIR "/usr/share/xiapin"
#endif
#ifndef XIAPIN_LIBIME_MODEL
#define XIAPIN_LIBIME_MODEL "/usr/lib/x86_64-linux-gnu/libime/zh_CN.lm"
#endif

namespace {

struct XiapinIBusEngine {
    IBusEngine parent;
    xiapin::EngineCore *core;
    bool shiftPending;
    bool sensitive;
};

struct XiapinIBusEngineClass {
    IBusEngineClass parent;
};

GType xiapin_ibus_engine_get_type();
std::vector<XiapinIBusEngine *> engines;
std::shared_ptr<const xiapin::EmojiIndex> emojiIndex;

#define XIAPIN_TYPE_IBUS_ENGINE (xiapin_ibus_engine_get_type())
#define XIAPIN_IBUS_ENGINE(object)                                             \
    (G_TYPE_CHECK_INSTANCE_CAST((object), XIAPIN_TYPE_IBUS_ENGINE,             \
                                XiapinIBusEngine))

G_DEFINE_TYPE(XiapinIBusEngine, xiapin_ibus_engine, IBUS_TYPE_ENGINE)

std::string userDataDirectory() {
    const char *xdg = std::getenv("XDG_DATA_HOME");
    if (xdg && *xdg) {
        return std::string(xdg) + "/xiapin";
    }
    const char *home = std::getenv("HOME");
    if (!home || !*home) {
        throw std::runtime_error("HOME is unavailable");
    }
    return std::string(home) + "/.local/share/xiapin";
}

std::string installedDataDirectory() {
    const char *overridePath = std::getenv("XIAPIN_DATA_DIR");
    return overridePath && *overridePath ? overridePath : XIAPIN_DATA_DIR;
}

xiapin::EngineCore *createCore(bool forceReload = false) {
    return new xiapin::EngineCore({
        "/usr/share/libime/sc.dict",
        installedDataDirectory() + "/xiapin-extra.dict",
        XIAPIN_LIBIME_MODEL,
        userDataDirectory(),
    }, forceReload, emojiIndex);
}

void render(XiapinIBusEngine *engine) {
    const auto view = engine->core->view();
    if (!view.visible) {
        ibus_engine_hide_preedit_text(IBUS_ENGINE(engine));
        ibus_engine_hide_lookup_table(IBUS_ENGINE(engine));
        return;
    }

    IBusText *preedit = ibus_text_new_from_string(view.preedit.c_str());
    ibus_engine_update_preedit_text(
        IBUS_ENGINE(engine), preedit,
        static_cast<guint>(
            xiapin::utf8CharacterOffset(view.preedit, view.cursorBytes)),
        TRUE);

    IBusLookupTable *table = ibus_lookup_table_new(9, 0, TRUE, FALSE);
    // GNOME inherits the global IBus panel preference for SYSTEM. Fresh
    // Ubuntu installations default that preference to vertical, which makes
    // a nine-item pinyin page unnecessarily tall. Xiapin consistently uses a
    // compact horizontal candidate row on every supported Ubuntu release.
    table->orientation = IBUS_ORIENTATION_HORIZONTAL;
    for (const auto &candidate : view.candidates) {
        ibus_lookup_table_append_candidate(
            table, ibus_text_new_from_string(candidate.c_str()));
    }
    if (!view.candidates.empty()) {
        ibus_lookup_table_set_cursor_pos(
            table, static_cast<guint>(view.candidateCursor));
        ibus_engine_update_lookup_table(IBUS_ENGINE(engine), table, TRUE);
    } else {
        g_object_unref(table);
        ibus_engine_hide_lookup_table(IBUS_ENGINE(engine));
    }
}

gboolean applyResult(XiapinIBusEngine *engine,
                     const xiapin::EngineResult &result) {
    if (!result.commit.empty()) {
        ibus_engine_commit_text(
            IBUS_ENGINE(engine),
            ibus_text_new_from_string(result.commit.c_str()));
    }
    if (result.changed || !result.commit.empty()) {
        render(engine);
    }
    return result.handled ? TRUE : FALSE;
}

bool isShift(guint keyval) {
    return keyval == IBUS_KEY_Shift_L || keyval == IBUS_KEY_Shift_R;
}

std::string punctuationFor(XiapinIBusEngine *engine, guint keyval) {
    if (!engine->core->view().chineseMode || keyval >= 128) {
        return {};
    }
    return xiapin::chinesePunctuation(static_cast<char>(keyval));
}

gboolean commitPunctuation(XiapinIBusEngine *engine,
                           const std::string &punctuation) {
    if (punctuation.empty()) {
        return FALSE;
    }
    if (engine->core->empty()) {
        ibus_engine_commit_text(
            IBUS_ENGINE(engine),
            ibus_text_new_from_string(punctuation.c_str()));
        return TRUE;
    }
    return applyResult(engine, engine->core->commitBestAndAppend(punctuation));
}

gboolean processKeyEvent(IBusEngine *base, guint keyval, guint,
                         guint state) {
    auto *engine = XIAPIN_IBUS_ENGINE(base);
    const bool release = (state & IBUS_RELEASE_MASK) != 0;

    if (isShift(keyval)) {
        if (!release) {
            engine->shiftPending = true;
            return FALSE;
        }
        if (engine->shiftPending) {
            engine->shiftPending = false;
            engine->core->toggleMode();
            render(engine);
            return FALSE;
        }
        return FALSE;
    }

    if (release) {
        return FALSE;
    }
    if (engine->shiftPending || (state & IBUS_SHIFT_MASK) != 0) {
        engine->shiftPending = false;
        if (const auto punctuation = punctuationFor(engine, keyval);
            !punctuation.empty()) {
            return commitPunctuation(engine, punctuation);
        }
        return FALSE;
    }

    const guint modifiers =
        state & (IBUS_CONTROL_MASK | IBUS_MOD1_MASK | IBUS_SUPER_MASK);
    if (keyval == IBUS_KEY_space && modifiers == IBUS_CONTROL_MASK) {
        engine->core->toggleMode();
        render(engine);
        return TRUE;
    }
    if (modifiers != 0) {
        return FALSE;
    }


    if (const auto punctuation = punctuationFor(engine, keyval);
        !punctuation.empty()) {
        return commitPunctuation(engine, punctuation);
    }

    if (keyval >= IBUS_KEY_a && keyval <= IBUS_KEY_z) {
        return applyResult(engine,
                           engine->core->type(static_cast<char>('a' +
                                                               keyval - IBUS_KEY_a)));
    }
    if (keyval == IBUS_KEY_apostrophe) {
        return applyResult(engine, engine->core->type('\''));
    }
    if (keyval >= IBUS_KEY_1 && keyval <= IBUS_KEY_9 &&
        !engine->core->empty()) {
        const auto page = engine->core->view().candidateCursor / 9;
        const auto index = page * 9 + (keyval - IBUS_KEY_1);
        return applyResult(engine, engine->core->selectCandidate(index));
    }

    switch (keyval) {
    case IBUS_KEY_space:
        // With no active composition, Space belongs to the application.
        // Calling selectCurrentCandidate() on an empty candidate list used to
        // report the key as handled and silently discard ordinary spaces.
        if (engine->core->empty()) {
            return FALSE;
        }
        return applyResult(engine, engine->core->selectCurrentCandidate());
    case IBUS_KEY_BackSpace:
        return applyResult(engine, engine->core->backspace());
    case IBUS_KEY_Delete:
        return applyResult(engine, engine->core->deleteForward());
    case IBUS_KEY_Left:
        return applyResult(engine, engine->core->moveLeft());
    case IBUS_KEY_Right:
        return applyResult(engine, engine->core->moveRight());
    case IBUS_KEY_Home:
        return applyResult(engine, engine->core->moveHome());
    case IBUS_KEY_End:
        return applyResult(engine, engine->core->moveEnd());
    case IBUS_KEY_Up:
        return applyResult(engine, engine->core->candidateUp());
    case IBUS_KEY_Down:
        return applyResult(engine, engine->core->candidateDown());
    case IBUS_KEY_Page_Up:
    case IBUS_KEY_minus:
        return applyResult(engine, engine->core->pageUp());
    case IBUS_KEY_Page_Down:
    case IBUS_KEY_equal:
        return applyResult(engine, engine->core->pageDown());
    case IBUS_KEY_Escape:
        return applyResult(engine, engine->core->escape());
    case IBUS_KEY_Return:
    case IBUS_KEY_KP_Enter:
        return applyResult(engine, engine->core->enter());
    default:
        break;
    }

    if (!engine->core->empty() && keyval < 128 && keyval >= 32) {
        return applyResult(
            engine,
            engine->core->commitBestAndAppend(
                std::string(1, static_cast<char>(keyval))));
    }
    return FALSE;
}

void reset(IBusEngine *base) {
    auto *engine = XIAPIN_IBUS_ENGINE(base);
    engine->core->reset();
    render(engine);
}

void focusOut(IBusEngine *base) { reset(base); }

void setContentType(IBusEngine *base, guint purpose, guint hints) {
    auto *engine = XIAPIN_IBUS_ENGINE(base);
    const bool sensitive =
        purpose == IBUS_INPUT_PURPOSE_PASSWORD ||
        purpose == IBUS_INPUT_PURPOSE_PIN ||
        (hints & IBUS_INPUT_HINT_PRIVATE) != 0;
    engine->sensitive = sensitive;
    engine->core->setSensitive(sensitive);
}

void candidateClicked(IBusEngine *base, guint index, guint button, guint) {
    if (button != 1) {
        return;
    }
    auto *engine = XIAPIN_IBUS_ENGINE(base);
    const auto page = engine->core->view().candidateCursor / 9;
    applyResult(engine, engine->core->selectCandidate(page * 9 + index));
}

void pageUp(IBusEngine *base) {
    auto *engine = XIAPIN_IBUS_ENGINE(base);
    applyResult(engine, engine->core->pageUp());
}

void pageDown(IBusEngine *base) {
    auto *engine = XIAPIN_IBUS_ENGINE(base);
    applyResult(engine, engine->core->pageDown());
}

void cursorUp(IBusEngine *base) {
    auto *engine = XIAPIN_IBUS_ENGINE(base);
    applyResult(engine, engine->core->candidateUp());
}

void cursorDown(IBusEngine *base) {
    auto *engine = XIAPIN_IBUS_ENGINE(base);
    applyResult(engine, engine->core->candidateDown());
}

void finalize(GObject *object) {
    auto *engine = XIAPIN_IBUS_ENGINE(object);
    engines.erase(std::remove(engines.begin(), engines.end(), engine),
                  engines.end());
    delete engine->core;
    engine->core = nullptr;
    G_OBJECT_CLASS(xiapin_ibus_engine_parent_class)->finalize(object);
}

void xiapin_ibus_engine_init(XiapinIBusEngine *engine) {
    engine->shiftPending = false;
    engine->sensitive = false;
    try {
        engine->core = createCore();
        engines.push_back(engine);
    } catch (const std::exception &error) {
        g_error("Xiapin engine initialization failed: %s", error.what());
    }
}

void xiapin_ibus_engine_class_init(XiapinIBusEngineClass *klass) {
    auto *engineClass = IBUS_ENGINE_CLASS(klass);
    engineClass->process_key_event = processKeyEvent;
    engineClass->reset = reset;
    engineClass->focus_out = focusOut;
    engineClass->set_content_type = setContentType;
    engineClass->candidate_clicked = candidateClicked;
    engineClass->page_up = pageUp;
    engineClass->page_down = pageDown;
    engineClass->cursor_up = cursorUp;
    engineClass->cursor_down = cursorDown;
    G_OBJECT_CLASS(klass)->finalize = finalize;
}

void disconnected(IBusBus *, gpointer) { ibus_quit(); }

gboolean reloadLearningData(gpointer) {
    bool forceReload = true;
    for (auto *engine : engines) {
        try {
            std::unique_ptr<xiapin::EngineCore> replacement(
                createCore(forceReload));
            forceReload = false;
            replacement->setSensitive(engine->sensitive);
            delete engine->core;
            engine->core = replacement.release();
            render(engine);
        } catch (const std::exception &error) {
            g_warning("Xiapin learning-data reload failed: %s", error.what());
        }
    }
    return G_SOURCE_CONTINUE;
}

} // namespace

bool registerComponent(IBusBus *bus) {
    const auto componentPath = installedDataDirectory() + "/xiapin.xml";
    IBusComponent *component =
        ibus_component_new_from_file(componentPath.c_str());
    if (!component) {
        g_printerr("Xiapin component metadata is invalid.\n");
        return false;
    }
    const gboolean registered = ibus_bus_register_component(bus, component);
    g_object_unref(component);
    if (!registered) {
        g_printerr("Xiapin could not register with the running IBus daemon.\n");
        return false;
    }
    return true;
}

int main(int argc, char **argv) {
    ibus_init();
    const bool dynamicRegister =
        argc == 2 && std::string(argv[1]) == "--register";
    const bool ibusLaunch = argc == 2 && std::string(argv[1]) == "--ibus";
    if (argc != 1 && !dynamicRegister && !ibusLaunch) {
        g_printerr("Usage: ibus-engine-xiapin [--ibus|--register]\n");
        return 2;
    }
    // Direct GVariant parsing takes about 15 ms on the largest supported
    // database and guarantees that the first composition can offer Emoji.
    try {
        emojiIndex = xiapin::EmojiIndex::load(
            "/usr/share/ibus/dicts/emoji-zh.dict");
    } catch (const std::exception &error) {
        g_warning("Xiapin Emoji data is unavailable: %s", error.what());
    }
    IBusBus *bus = ibus_bus_new();
    if (!ibus_bus_is_connected(bus)) {
        g_printerr("Xiapin cannot connect to IBus.\n");
        g_object_unref(bus);
        return 1;
    }
    g_signal_connect(bus, "disconnected", G_CALLBACK(disconnected), nullptr);
    IBusFactory *factory = ibus_factory_new(ibus_bus_get_connection(bus));
    ibus_factory_add_engine(factory, "xiapin", XIAPIN_TYPE_IBUS_ENGINE);
    const guint32 nameFlags = dynamicRegister
                                  ? IBUS_BUS_NAME_FLAG_ALLOW_REPLACEMENT |
                                        IBUS_BUS_NAME_FLAG_REPLACE_EXISTING |
                                        IBUS_BUS_NAME_FLAG_DO_NOT_QUEUE
                                  : 0;
    const guint32 reply = ibus_bus_request_name(
        bus, "org.freedesktop.IBus.Xiapin", nameFlags);
    if (reply != IBUS_BUS_REQUEST_NAME_REPLY_PRIMARY_OWNER &&
        reply != IBUS_BUS_REQUEST_NAME_REPLY_ALREADY_OWNER) {
        g_printerr("Xiapin cannot own its IBus service name.\n");
        g_object_unref(factory);
        g_object_unref(bus);
        return 1;
    }
    if (dynamicRegister && !registerComponent(bus)) {
        g_object_unref(factory);
        g_object_unref(bus);
        return 1;
    }
    g_unix_signal_add(SIGHUP, reloadLearningData, nullptr);
    ibus_main();
    g_object_unref(factory);
    g_object_unref(bus);
    return 0;
}
